import json
import re
from typing import Any, Dict, List
import requests
from app.core.config import settings
from app.models.schemas import EntityExtraction


def _ollama_generate(prompt: str, temperature: float = 0.1) -> str:
    if not settings.llm_enabled:
        raise RuntimeError("LLM is disabled. Set LLM_ENABLED=true in backend/.env and run Ollama.")

    url = f"{settings.ollama_host.rstrip('/')}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    response = requests.post(url, json=payload, timeout=settings.llm_timeout_seconds)
    response.raise_for_status()
    return response.json().get("response", "").strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1)
    else:
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first:last + 1]
    return json.loads(text)


def _listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        parts = re.split(r"[,;|]", value)
        return [p.strip() for p in parts if p.strip()]
    return []


def extract_entities_with_llm(text: str, fallback: EntityExtraction | None = None) -> EntityExtraction:
    sample = text[:12000]
    prompt = f"""
You are an information extraction system for research papers.
Extract structured metadata from the paper text.
Return only valid JSON. Do not add commentary.

Schema:
{{
  "title": "string",
  "authors": ["string"],
  "methods": ["string"],
  "datasets": ["string"],
  "models": ["string"],
  "keywords": ["string"],
  "topics": ["string"],
  "abstract": "string or null"
}}

Rules:
- Use exact names when visible.
- Keep lists short and useful.
- Do not invent datasets, models, or authors.
- If missing, use an empty list or null.

Paper text:
{sample}
""".strip()

    try:
        raw = _ollama_generate(prompt)
        data = _extract_json_object(raw)
        return EntityExtraction(
            title=str(data.get("title") or (fallback.title if fallback else "Unknown Title")),
            authors=_listify(data.get("authors")) or (fallback.authors if fallback else []),
            methods=_listify(data.get("methods")) or (fallback.methods if fallback else []),
            datasets=_listify(data.get("datasets")) or (fallback.datasets if fallback else []),
            models=_listify(data.get("models")) or (fallback.models if fallback else []),
            keywords=_listify(data.get("keywords")) or (fallback.keywords if fallback else []),
            topics=_listify(data.get("topics")) or (fallback.topics if fallback else []),
            abstract=data.get("abstract") or (fallback.abstract if fallback else None),
        )
    except Exception:
        if fallback:
            return fallback
        raise


def generate_sparql_from_question(question: str) -> str:
    prompt = f"""
Convert the user question into a SPARQL SELECT query for this RDF graph.
Return only the SPARQL query, no markdown.

Prefixes:
PREFIX pg: <https://example.org/papergraph/>
PREFIX schema: <https://schema.org/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

Important predicates:
- dcterms:title for paper title
- dcterms:creator for authors
- pg:usesMethod for methods
- pg:usesDataset for datasets
- pg:usesModel for models
- pg:studiesTopic for topics
- schema:keywords for keywords
- rdfs:label for labels of connected entities

Question: {question}
""".strip()
    sparql = _ollama_generate(prompt, temperature=0.0)
    sparql = re.sub(r"```(?:sparql)?", "", sparql, flags=re.I).replace("```", "").strip()
    if not sparql.lower().startswith("prefix") and "select" not in sparql.lower():
        raise RuntimeError("The LLM did not return a valid SPARQL query.")
    return sparql


def answer_question_with_evidence(question: str, evidence_rows: List[Dict[str, Any]]) -> str:
    evidence = json.dumps(evidence_rows[:20], indent=2, ensure_ascii=False)
    prompt = f"""
Answer the question using only the evidence from the knowledge graph.
If the evidence is empty or insufficient, say that the graph does not contain enough information.
Keep the answer concise and cite the relevant labels/values from the evidence.

Question:
{question}

Evidence:
{evidence}
""".strip()
    try:
        return _ollama_generate(prompt, temperature=0.2)
    except Exception:
        if not evidence_rows:
            return "The graph does not contain enough information to answer this question."
        return f"I found {len(evidence_rows)} matching knowledge graph result(s). Review the evidence table for details."
