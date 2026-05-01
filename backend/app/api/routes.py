import json
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from app.core.config import settings
from app.models.schemas import (
    HealthResponse,
    PaperResponse,
    UpdateEntitiesRequest,
    UpdateEntitiesResponse,
    SparqlRequest,
    SparqlResponse,
    GenerateSparqlRequest,
    GenerateSparqlResponse,
    QARequest,
    QAResponse,
)
from app.services.pdf_service import extract_text_from_pdf
from app.services.extraction_service import extract_entities
from app.services.llm_service import extract_entities_with_llm, generate_sparql_from_question, answer_question_with_evidence
from app.services.rdf_service import build_graph, graph_to_triples, save_graph_exports, load_graph, run_sparql_query, default_evidence_query
from app.services.fuseki_service import upload_graph_to_fuseki

router = APIRouter()


def _paper_dir(paper_id: str) -> Path:
    return settings.storage_dir / paper_id


def _metadata_path(paper_id: str) -> Path:
    return _paper_dir(paper_id) / "metadata.json"


def _export_urls(paper_id: str) -> dict:
    return {
        "ttl": f"/api/papers/{paper_id}/export?format=ttl",
        "rdf": f"/api/papers/{paper_id}/export?format=rdf",
        "jsonld": f"/api/papers/{paper_id}/export?format=jsonld",
    }


def _write_metadata(paper_id: str, filename: str, extractor: str, entities, triples):
    metadata = {
        "paper_id": paper_id,
        "filename": filename,
        "extractor": extractor,
        "entities": entities.model_dump(),
        "triples": [triple.model_dump() for triple in triples],
        "export_urls": _export_urls(paper_id),
    }
    _metadata_path(paper_id).write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        llm_enabled=settings.llm_enabled,
    )


@router.post("/upload", response_model=PaperResponse)
async def upload_paper(
    file: UploadFile = File(...),
    extractor: str = Query("hybrid", pattern="^(rule|llm|hybrid)$"),
    upload_to_fuseki: bool = False,
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    paper_id = str(uuid.uuid4())[:8]
    paper_dir = _paper_dir(paper_id)
    paper_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = paper_dir / file.filename

    with pdf_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        text = extract_text_from_pdf(pdf_path)
        if not text:
            raise HTTPException(status_code=422, detail="No extractable text found in PDF. OCR is not included yet.")

        rule_entities = extract_entities(text)
        if extractor == "rule":
            entities = rule_entities
        elif extractor == "llm":
            entities = extract_entities_with_llm(text, fallback=rule_entities)
        else:
            entities = extract_entities_with_llm(text, fallback=rule_entities) if settings.llm_enabled else rule_entities

        graph = build_graph(paper_id, entities)
        save_graph_exports(graph, paper_id, settings.storage_dir)
        triples = graph_to_triples(graph)

        _write_metadata(paper_id, file.filename, extractor, entities, triples)
        (paper_dir / "extracted_text.txt").write_text(text, encoding="utf-8")

        if upload_to_fuseki:
            try:
                upload_graph_to_fuseki(graph)
            except Exception as exc:
                (paper_dir / "fuseki_error.txt").write_text(str(exc), encoding="utf-8")

        return PaperResponse(
            paper_id=paper_id,
            filename=file.filename,
            extractor=extractor,
            entities=entities,
            triples=triples,
            export_urls=_export_urls(paper_id),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {exc}")


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    metadata_path = _metadata_path(paper_id)
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Paper not found")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


@router.get("/papers/{paper_id}/text", response_class=PlainTextResponse)
def get_extracted_text(paper_id: str):
    path = _paper_dir(paper_id) / "extracted_text.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Extracted text not found")
    return path.read_text(encoding="utf-8")


@router.put("/papers/{paper_id}/entities", response_model=UpdateEntitiesResponse)
def update_entities(paper_id: str, request: UpdateEntitiesRequest):
    metadata_path = _metadata_path(paper_id)
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Paper not found")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    graph = build_graph(paper_id, request.entities)
    save_graph_exports(graph, paper_id, settings.storage_dir)
    triples = graph_to_triples(graph)
    _write_metadata(paper_id, metadata.get("filename", "unknown.pdf"), "human_corrected", request.entities, triples)

    if request.upload_to_fuseki:
        try:
            upload_graph_to_fuseki(graph)
        except Exception as exc:
            (_paper_dir(paper_id) / "fuseki_error.txt").write_text(str(exc), encoding="utf-8")

    return UpdateEntitiesResponse(
        paper_id=paper_id,
        entities=request.entities,
        triples=triples,
        export_urls=_export_urls(paper_id),
    )


@router.get("/papers/{paper_id}/export")
def export_graph(paper_id: str, format: str = "ttl"):
    allowed = {"ttl": "graph.ttl", "rdf": "graph.rdf", "jsonld": "graph.jsonld"}
    if format not in allowed:
        raise HTTPException(status_code=400, detail="Format must be one of: ttl, rdf, jsonld")

    path = _paper_dir(paper_id) / allowed[format]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found")

    media_types = {
        "ttl": "text/turtle",
        "rdf": "application/rdf+xml",
        "jsonld": "application/ld+json",
    }
    return FileResponse(path, media_type=media_types[format], filename=allowed[format])


@router.post("/papers/{paper_id}/sparql", response_model=SparqlResponse)
def query_paper_graph(paper_id: str, request: SparqlRequest):
    try:
        graph = load_graph(paper_id, settings.storage_dir)
        data = run_sparql_query(graph, request.query)
        return SparqlResponse(**data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Graph not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"SPARQL query failed: {exc}")


@router.post("/papers/{paper_id}/generate-sparql", response_model=GenerateSparqlResponse)
def generate_sparql(paper_id: str, request: GenerateSparqlRequest):
    if not _metadata_path(paper_id).exists():
        raise HTTPException(status_code=404, detail="Paper not found")
    try:
        sparql = generate_sparql_from_question(request.question)
        return GenerateSparqlResponse(question=request.question, sparql=sparql)
    except Exception as exc:
        fallback = default_evidence_query(request.question)
        return GenerateSparqlResponse(question=request.question, sparql=fallback)


@router.post("/papers/{paper_id}/qa", response_model=QAResponse)
def ask_graph(paper_id: str, request: QARequest):
    try:
        graph = load_graph(paper_id, settings.storage_dir)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Graph not found")

    try:
        sparql = generate_sparql_from_question(request.question) if settings.llm_enabled else default_evidence_query(request.question)
    except Exception:
        sparql = default_evidence_query(request.question)

    try:
        evidence_data = run_sparql_query(graph, sparql)
    except Exception:
        sparql = default_evidence_query(request.question)
        evidence_data = run_sparql_query(graph, sparql)

    evidence_rows = evidence_data["rows"]
    answer = answer_question_with_evidence(request.question, evidence_rows) if settings.llm_enabled else _rule_based_answer(request.question, evidence_rows)

    return QAResponse(
        question=request.question,
        answer=answer,
        sparql=sparql if request.include_generated_sparql else None,
        evidence=evidence_rows,
    )


def _rule_based_answer(question: str, rows: list[dict]) -> str:
    if not rows:
        return "The knowledge graph does not contain enough information to answer this question."
    values = []
    for row in rows:
        for key, value in row.items():
            if key.lower() not in {"paper", "papertitle", "predicate"} and value:
                values.append(str(value))
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    if unique:
        return "The graph contains these relevant items: " + ", ".join(unique[:15])
    return f"I found {len(rows)} matching result(s) in the graph."
