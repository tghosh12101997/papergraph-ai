from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


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
    filename: str
    extractor: str
    entities: EntityExtraction
    triples: List[TripleItem]
    export_urls: Dict[str, str]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_enabled: bool


class UpdateEntitiesRequest(BaseModel):
    entities: EntityExtraction
    upload_to_fuseki: bool = False


class UpdateEntitiesResponse(BaseModel):
    paper_id: str
    entities: EntityExtraction
    triples: List[TripleItem]
    export_urls: Dict[str, str]


class SparqlRequest(BaseModel):
    query: str


class SparqlResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    raw_count: int


class GenerateSparqlRequest(BaseModel):
    question: str


class GenerateSparqlResponse(BaseModel):
    question: str
    sparql: str


class QARequest(BaseModel):
    question: str
    include_generated_sparql: bool = True


class QAResponse(BaseModel):
    question: str
    answer: str
    sparql: Optional[str] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
