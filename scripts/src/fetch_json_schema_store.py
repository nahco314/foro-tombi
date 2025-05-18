import asyncio
import json

import httpx

from model import Catalog, Schema

catalog_url = "https://www.schemastore.org/api/json/catalog.json"


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

        tasks = [
            fetch_schema(client, schema)
            for schema in catalog.schemas
            if contains_toml(schema)
        ]
        results = await asyncio.gather(*tasks)

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
