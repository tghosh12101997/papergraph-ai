# PaperGraph AI: Research Paper to Knowledge Graph Builder

PaperGraph AI is a portfolio-ready Knowledge Graph + AI project. It lets users upload a research paper PDF, extracts useful research entities, converts them into RDF triples, visualizes the graph, and exports the graph as Turtle, RDF/XML, or JSON-LD.

## Features

- Upload PDF research papers
- Extract title, authors, methods, datasets, models, keywords, topics, and abstract
- Convert extracted entities into RDF triples
- Export graph as `.ttl`, `.rdf`, and `.jsonld`
- Visualize the graph interactively using Streamlit + Pyvis
- Optional Apache Jena Fuseki service through Docker Compose

## Architecture

```text
PDF Upload
   ↓
FastAPI Backend
   ↓
PyMuPDF Text Extraction
   ↓
Entity Extraction
   ↓
RDFLib Knowledge Graph Builder
   ↓
Local RDF Exports + Optional Fuseki
   ↓
Streamlit UI Visualization
```

## File Structure

```text
PaperGraphAI/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── models/
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── extraction_service.py
│   │   │   ├── fuseki_service.py
│   │   │   ├── pdf_service.py
│   │   │   └── rdf_service.py
│   │   ├── storage/
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py
│   └── requirements.txt
├── ontology/
│   └── papergraph_ontology.ttl
├── docs/
├── data/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Local Setup

### 1. Create and activate virtual environment

```bash
cd PaperGraphAI
python -m venv .venv

# Windows PowerShell
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

Optional spaCy model:

```bash
python -m spacy download en_core_web_sm
```

The project still works without this model because it has fallback extraction logic.

### 3. Run backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/docs
```

### 4. Run frontend

Open a second terminal:

```bash
cd PaperGraphAI/frontend
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## Docker Setup

Run backend and Fuseki:

```bash
cd PaperGraphAI
docker compose up --build
```

Backend:

```text
http://localhost:8000
```

Fuseki:

```text
http://localhost:3030
```

Default Fuseki admin password from `docker-compose.yml`:

```text
admin
```

## API Endpoints

### Health Check

```http
GET /api/health
```

### Upload PDF

```http
POST /api/upload
```

Form-data:

```text
file: research-paper.pdf
```

### Get Paper Metadata

```http
GET /api/papers/{paper_id}
```

### Export RDF

```http
GET /api/papers/{paper_id}/export?format=ttl
GET /api/papers/{paper_id}/export?format=rdf
GET /api/papers/{paper_id}/export?format=jsonld
```

## Example Knowledge Graph Pattern

```text
Paper → hasAuthor → Author
Paper → usesMethod → Method
Paper → studiesTopic → Topic
Paper → usesDataset → Dataset
Paper → usesModel → Model
Paper → hasKeyword → Keyword
```

## What to Show in Your Portfolio

Include these screenshots:

1. Upload page
2. Extracted entities
3. Interactive graph visualization
4. RDF triples table
5. Turtle / JSON-LD export
6. Swagger API docs

## Future Work

- Add OCR for scanned PDFs
- Add LLM-based entity extraction
- Add human correction UI before RDF generation
- Add SPARQL query interface
- Add GraphRAG question answering
- Add Neo4j or GraphDB support
- Add paper recommendation system

## Notes

This MVP uses rule-based extraction so that the project runs locally without paid APIs. The next version can add Ollama or OpenAI to improve extraction quality.
