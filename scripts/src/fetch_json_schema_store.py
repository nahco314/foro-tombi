import asyncio
import json
from typing import Any, Dict, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse
import httpx
from model import Catalog, Schema

catalog_url = "https://www.schemastore.org/api/json/catalog.json"


class SchemaResolver:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.cache: Dict[str, Tuple[Optional[Dict[str, Any]], bool]] = {}
        self.in_progress: Set[str] = set()

    async def fetch_external_schema(self, url: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Fetch an external schema and check if it contains 'tombi'."""
        if url in self.cache:
            return self.cache[url]

        # Prevent infinite recursion
        if url in self.in_progress:
            return None, False

        self.in_progress.add(url)

        try:
            res = await self.client.get(url, timeout=30.0)
            if res.status_code == 404:
                # Skip 404s as requested
                result = (None, False)
            else:
                res.raise_for_status()
                content = res.text
                contains_tombi = "tombi" in content
                try:
                    schema_dict = json.loads(content)
                    result = (schema_dict, contains_tombi)
                except json.JSONDecodeError:
                    result = (None, False)
        except Exception:
            # Handle any other errors (network issues, timeouts, etc.)
            result = (None, False)

        self.in_progress.remove(url)
        self.cache[url] = result
        return result

    async def resolve_refs(self, schema: Dict[str, Any], base_url: str) -> Tuple[Dict[str, Any], bool]:
        """
        Recursively resolve only external URL $ref references in a schema.
        Internal references (#/...) are kept as-is for tombi to handle.
        Returns the resolved schema and whether it (or its dependencies) contains 'tombi'.
        Tree-shaking happens at the external URL resolution level.
        """
        if not isinstance(schema, dict):
            return schema, False

        # Check if this object contains a $ref
        if "$ref" in schema and isinstance(schema["$ref"], str):
            ref = schema["$ref"]
            if ref.startswith("#"):
                # Internal reference - keep the entire object as-is for tombi to handle
                return schema, False
            else:
                # External reference
                absolute_url = urljoin(base_url, ref)
                external_schema, external_contains_tombi = await self.fetch_external_schema(absolute_url)

                if external_schema:
                    # Tree-shaking: only include external schemas that contain tombi
                    if external_contains_tombi:
                        # Recursively resolve refs in the fetched schema
                        resolved_external, transitive_tombi = await self.resolve_refs(external_schema, absolute_url)
                        # In JSON Schema draft-07, $ref replaces the entire object
                        return resolved_external, True
                    else:
                        # External schema doesn't contain tombi - tree-shake it
                        # Return empty object to replace the $ref object
                        return {}, False
                else:
                    # Failed to fetch (404, etc.) - return empty object
                    return {}, False

        # No $ref in this object, process all properties recursively
        contains_tombi_transitively = False
        resolved_schema = {}

        for key, value in schema.items():
            if isinstance(value, dict):
                resolved_value, child_contains_tombi = await self.resolve_refs(value, base_url)
                resolved_schema[key] = resolved_value
                contains_tombi_transitively = contains_tombi_transitively or child_contains_tombi
            elif isinstance(value, list):
                resolved_list = []
                for item in value:
                    if isinstance(item, dict):
                        resolved_item, item_contains_tombi = await self.resolve_refs(item, base_url)
                        resolved_list.append(resolved_item)
                        contains_tombi_transitively = contains_tombi_transitively or item_contains_tombi
                    else:
                        resolved_list.append(item)
                resolved_schema[key] = resolved_list
            else:
                resolved_schema[key] = value

        return resolved_schema, contains_tombi_transitively


async def fetch_schema(client: httpx.AsyncClient, schema: Schema) -> tuple[Schema, str]:
    res = await client.get(schema.url)
    content = res.text
    return schema, content


def contains_toml(schema: Schema) -> bool:
    return any("toml" in p for p in schema.file_match)


async def fetch_all() -> list[tuple[Schema, str]]:
    async with httpx.AsyncClient() as client:
        catalog_res = await client.get(catalog_url, follow_redirects=True)
        catalog = Catalog.model_validate(catalog_res.json())

        resolver = SchemaResolver(client)

        # Fetch and resolve all TOML schemas
        toml_schemas = [schema for schema in catalog.schemas if contains_toml(schema)]

        results = []
        for schema in toml_schemas:
            try:
                res = await client.get(schema.url)
                content = res.text

                content = json.dumps(json.loads(content))

                # Try to parse and resolve refs
                try:
                    schema_dict = json.loads(content)
                    resolved_schema, contains_tombi_transitively = await resolver.resolve_refs(schema_dict, schema.url)

                    # Convert back to string
                    resolved_content = json.dumps(resolved_schema)

                    # Add to results - main() will filter for tombi
                    results.append((schema, resolved_content))
                except json.JSONDecodeError:
                    # If we can't parse as JSON, keep original content
                    results.append((schema, content))
            except Exception:
                # Skip schemas that fail to fetch (404s, network errors, etc.)
                continue

        return results


def main() -> None:
    results = asyncio.run(fetch_all())
    tombi_schemas = [r for r in results if "tombi" in r[1]]
    dump_result = [
        {"url": r[0].url, "file_match": json.dumps(r[0].file_match), "content": r[1]}
        for r in tombi_schemas
    ]
    print(json.dumps(dump_result))


if __name__ == "__main__":
    main()
