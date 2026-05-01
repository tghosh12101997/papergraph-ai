import re
from pathlib import Path
from typing import List, Dict, Any
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, DCTERMS, FOAF
from app.core.config import settings
from app.models.schemas import EntityExtraction, TripleItem

PG = Namespace(settings.base_uri)
SCHEMA = Namespace("https://schema.org/")

PREFIXES = """
PREFIX pg: <https://example.org/papergraph/>
PREFIX schema: <https://schema.org/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
""".strip()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


def bind_namespaces(g: Graph) -> Graph:
    g.bind("pg", PG)
    g.bind("schema", SCHEMA)
    g.bind("dcterms", DCTERMS)
    g.bind("foaf", FOAF)
    g.bind("rdfs", RDFS)
    return g


def build_graph(paper_id: str, entities: EntityExtraction) -> Graph:
    g = bind_namespaces(Graph())
    paper_uri = PG[f"paper/{paper_id}"]
    g.add((paper_uri, RDF.type, SCHEMA.ScholarlyArticle))
    g.add((paper_uri, DCTERMS.identifier, Literal(paper_id)))
    g.add((paper_uri, DCTERMS.title, Literal(entities.title)))
    if entities.abstract:
        g.add((paper_uri, DCTERMS.abstract, Literal(entities.abstract)))

    def add_entity(collection: str, rdf_type: URIRef, predicate: URIRef, label: str):
        label = label.strip()
        if not label:
            return
        entity_uri = PG[f"{collection}/{slugify(label)}"]
        g.add((entity_uri, RDF.type, rdf_type))
        g.add((entity_uri, RDFS.label, Literal(label)))
        g.add((paper_uri, predicate, entity_uri))

    for author in entities.authors:
        add_entity("author", FOAF.Person, DCTERMS.creator, author)
    for method in entities.methods:
        add_entity("method", PG.Method, PG.usesMethod, method)
    for dataset in entities.datasets:
        add_entity("dataset", PG.Dataset, PG.usesDataset, dataset)
    for model in entities.models:
        add_entity("model", PG.Model, PG.usesModel, model)
    for keyword in entities.keywords:
        if keyword.strip():
            g.add((paper_uri, SCHEMA.keywords, Literal(keyword.strip())))
    for topic in entities.topics:
        add_entity("topic", PG.Topic, PG.studiesTopic, topic)

    return g


def graph_to_triples(g: Graph) -> List[TripleItem]:
    triples = []
    for s, p, o in g:
        triples.append(TripleItem(subject=str(s), predicate=str(p), object=str(o)))
    return sorted(triples, key=lambda t: (t.subject, t.predicate, t.object))


def save_graph_exports(g: Graph, paper_id: str, out_dir: Path) -> dict:
    paper_dir = out_dir / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "ttl": paper_dir / "graph.ttl",
        "rdf": paper_dir / "graph.rdf",
        "jsonld": paper_dir / "graph.jsonld",
    }
    g.serialize(destination=str(files["ttl"]), format="turtle")
    g.serialize(destination=str(files["rdf"]), format="xml")
    g.serialize(destination=str(files["jsonld"]), format="json-ld", indent=2)
    return {fmt: str(path) for fmt, path in files.items()}


def load_graph(paper_id: str, storage_dir: Path) -> Graph:
    path = storage_dir / paper_id / "graph.ttl"
    if not path.exists():
        raise FileNotFoundError(f"No graph export found for paper_id={paper_id}")
    g = bind_namespaces(Graph())
    g.parse(path, format="turtle")
    return g


def run_sparql_query(g: Graph, query: str) -> Dict[str, Any]:
    result = g.query(query)
    columns = [str(var) for var in result.vars]
    rows = []
    for row in result:
        item = {}
        for idx, col in enumerate(columns):
            value = row[idx]
            item[col] = str(value) if value is not None else None
        rows.append(item)
    return {"columns": columns, "rows": rows, "raw_count": len(rows)}


def default_evidence_query(question: str) -> str:
    q = question.lower()
    if "author" in q:
        return PREFIXES + """
SELECT ?paperTitle ?authorLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         dcterms:creator ?author .
  ?author rdfs:label ?authorLabel .
}
LIMIT 50
"""
    if "dataset" in q:
        return PREFIXES + """
SELECT ?paperTitle ?datasetLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         pg:usesDataset ?dataset .
  ?dataset rdfs:label ?datasetLabel .
}
LIMIT 50
"""
    if "model" in q:
        return PREFIXES + """
SELECT ?paperTitle ?modelLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         pg:usesModel ?model .
  ?model rdfs:label ?modelLabel .
}
LIMIT 50
"""
    if "method" in q or "approach" in q:
        return PREFIXES + """
SELECT ?paperTitle ?methodLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         pg:usesMethod ?method .
  ?method rdfs:label ?methodLabel .
}
LIMIT 50
"""
    if "topic" in q:
        return PREFIXES + """
SELECT ?paperTitle ?topicLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         pg:studiesTopic ?topic .
  ?topic rdfs:label ?topicLabel .
}
LIMIT 50
"""
    return PREFIXES + """
SELECT ?paperTitle ?predicate ?object WHERE {
  ?paper dcterms:title ?paperTitle ;
         ?predicate ?object .
}
LIMIT 80
"""
