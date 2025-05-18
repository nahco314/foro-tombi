from pydantic import BaseModel, Field


class Schema(BaseModel):
    name: str
    description: str
    file_match: list[str] = Field(alias="fileMatch", default_factory=list)
    url: str
    versions: dict[str, str] = Field(default_factory=dict)


class Catalog(BaseModel):
    version: int
    schemas: list[Schema]
