# PaperGraph AI v2

Research paper PDF → entity extraction → RDF knowledge graph → graph visualization → SPARQL → GraphRAG-style QA.

This is Version 2 of the portfolio project. It keeps the simple local MVP but adds:

- optional LLM-assisted extraction through Ollama
- human correction screen in Streamlit
- RDF export as Turtle, RDF/XML, and JSON-LD
- local SPARQL query endpoint
- natural language to SPARQL generation
- GraphRAG-style QA using graph evidence
- optional Apache Jena Fuseki upload

## Architecture

```text
PDF Upload
   ↓
FastAPI backend
   ↓
PyMuPDF text extraction
   ↓
Rule-based extraction + optional Ollama LLM extraction
   ↓
Human correction screen
   ↓
RDFLib graph builder
   ↓
TTL / RDF / JSON-LD export
   ↓
SPARQL + Graph QA + Visualization
```

## File structure

```text
PaperGraphAI_v2/
├── backend/
│   ├── app/
│   │   ├── api/routes.py
│   │   ├── core/config.py
│   │   ├── models/schemas.py
│   │   ├── services/
│   │   │   ├── extraction_service.py
│   │   │   ├── fuseki_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── pdf_service.py
│   │   │   └── rdf_service.py
│   │   ├── storage/
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py
│   └── requirements.txt
├── ontology/papergraph_ontology.ttl
├── docs/architecture.md
├── scripts/run_backend.sh
├── scripts/run_frontend.sh
├── docker-compose.yml
├── .env.example
└── README.md
```

## Run locally without Docker

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/docs
```

### 2. Frontend

Open another terminal:

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## Enable local LLM extraction with Ollama

Install Ollama, then pull a model:

```bash
ollama pull llama3.1:8b
```

Edit `backend/.env`:

```env
LLM_ENABLED=true
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

Restart the backend.

If you run the backend inside Docker and Ollama runs on your host machine, use:

```env
OLLAMA_HOST=http://host.docker.internal:11434
```

## Optional Fuseki

Run:

```bash
docker compose up fuseki
```

Open:

```text
http://localhost:3030
```

Use username/password depending on the image defaults. The admin password is set to `admin` in `docker-compose.yml`.

Then edit `.env`:

```env
FUSEKI_ENABLED=true
FUSEKI_DATASET_URL=http://localhost:3030/papergraph
```

## Useful API endpoints

```text
GET  /api/health
POST /api/upload?extractor=hybrid
GET  /api/papers/{paper_id}
GET  /api/papers/{paper_id}/text
PUT  /api/papers/{paper_id}/entities
GET  /api/papers/{paper_id}/export?format=ttl
POST /api/papers/{paper_id}/sparql
POST /api/papers/{paper_id}/generate-sparql
POST /api/papers/{paper_id}/qa
```

## Example SPARQL

```sparql
PREFIX pg: <https://example.org/papergraph/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?paperTitle ?methodLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         pg:usesMethod ?method .
  ?method rdfs:label ?methodLabel .
}
LIMIT 50
```

## Portfolio talking points

- Built a research-paper-to-knowledge-graph pipeline.
- Extracted authors, methods, datasets, models, topics, and keywords.
- Modeled the output as RDF triples using RDFLib.
- Added human-in-the-loop correction before graph finalization.
- Added SPARQL querying and graph-grounded QA.
- Designed the project so it can later support multi-paper search, GraphRAG, and ontology alignment.
