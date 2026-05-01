from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class EntityExtraction(BaseModel):
    title: str = "Unknown Title"
    authors: List[str] = Field(default_factory=list)
    methods: List[str] = Field(default_factory=list)
    datasets: List[str] = Field(default_factory=list)
    models: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None


class TripleItem(BaseModel):
    subject: str
    predicate: str
    object: str


class PaperResponse(BaseModel):
    paper_id: str
    entities: EntityExtraction
    triples: List[TripleItem]
    export_urls: Dict[str, str]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
