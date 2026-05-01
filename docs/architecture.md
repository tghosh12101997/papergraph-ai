# Architecture

## Version 2 flow

```text
User uploads PDF
    ↓
FastAPI receives PDF
    ↓
PyMuPDF extracts text
    ↓
Rule-based extractor creates baseline entities
    ↓
Optional Ollama LLM improves extracted entities
    ↓
Streamlit correction screen allows human validation
    ↓
RDFLib creates RDF triples
    ↓
Graph is exported as TTL, RDF/XML, JSON-LD
    ↓
User can visualize graph, run SPARQL, or ask questions
```

## Main components

### Backend

FastAPI exposes the API endpoints and manages the processing pipeline.

### PDF service

Uses PyMuPDF to extract text from PDF pages.

### Extraction service

Uses rules, regex patterns, keyword matching, and optional spaCy to extract metadata.

### LLM service

Uses local Ollama to improve extraction, generate SPARQL, and write answers from graph evidence.

### RDF service

Uses RDFLib to create RDF triples and run local SPARQL queries.

### Frontend

Streamlit provides upload, correction, graph visualization, SPARQL, QA, and export screens.

## Current limitations

- No OCR for scanned PDFs yet.
- LLM output depends on the local model quality.
- Extraction is best for English academic PDFs.
- Multi-paper graph search is not included yet.

## Next upgrade

- Add OCR with PaddleOCR or Tesseract.
- Add multi-paper project workspace.
- Add Neo4j or GraphDB support.
- Add vector search for abstracts.
- Add ontology alignment to schema.org, FOAF, Dublin Core, and domain ontologies.
