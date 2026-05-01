import json
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.core.config import settings
from app.models.schemas import HealthResponse, PaperResponse
from app.services.pdf_service import extract_text_from_pdf
from app.services.extraction_service import extract_entities
from app.services.rdf_service import build_graph, graph_to_triples, save_graph_exports
from app.services.fuseki_service import upload_graph_to_fuseki

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


@router.post("/upload", response_model=PaperResponse)
async def upload_paper(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    paper_id = str(uuid.uuid4())[:8]
    paper_dir = settings.storage_dir / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = paper_dir / file.filename

    with pdf_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        text = extract_text_from_pdf(pdf_path)
        if not text:
            raise HTTPException(status_code=422, detail="No extractable text found in PDF. OCR is not included in this MVP.")

        entities = extract_entities(text)
        graph = build_graph(paper_id, entities)
        save_graph_exports(graph, paper_id, settings.storage_dir)
        triples = graph_to_triples(graph)

        metadata = {
            "paper_id": paper_id,
            "filename": file.filename,
            "entities": entities.model_dump(),
            "triples": [triple.model_dump() for triple in triples],
        }
        (paper_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (paper_dir / "extracted_text.txt").write_text(text, encoding="utf-8")

        try:
            upload_graph_to_fuseki(graph)
        except Exception as exc:
            # Keep MVP usable even if Fuseki is not running.
            (paper_dir / "fuseki_error.txt").write_text(str(exc), encoding="utf-8")

        export_urls = {
            "ttl": f"/api/papers/{paper_id}/export?format=ttl",
            "rdf": f"/api/papers/{paper_id}/export?format=rdf",
            "jsonld": f"/api/papers/{paper_id}/export?format=jsonld",
        }
        return PaperResponse(paper_id=paper_id, entities=entities, triples=triples, export_urls=export_urls)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {exc}")


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    metadata_path = settings.storage_dir / paper_id / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Paper not found")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


@router.get("/papers/{paper_id}/export")
def export_graph(paper_id: str, format: str = "ttl"):
    allowed = {"ttl": "graph.ttl", "rdf": "graph.rdf", "jsonld": "graph.jsonld"}
    if format not in allowed:
        raise HTTPException(status_code=400, detail="Format must be one of: ttl, rdf, jsonld")

    path = settings.storage_dir / paper_id / allowed[format]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found")

    media_types = {
        "ttl": "text/turtle",
        "rdf": "application/rdf+xml",
        "jsonld": "application/ld+json",
    }
    return FileResponse(path, media_type=media_types[format], filename=allowed[format])
