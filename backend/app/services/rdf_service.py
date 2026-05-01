import re
from pathlib import Path
from typing import List
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, DCTERMS, FOAF, XSD
from app.core.config import settings
from app.models.schemas import EntityExtraction, TripleItem

PG = Namespace(settings.base_uri)
SCHEMA = Namespace("https://schema.org/")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


def build_graph(paper_id: str, entities: EntityExtraction) -> Graph:
    g = Graph()
    g.bind("pg", PG)
    g.bind("schema", SCHEMA)
    g.bind("dcterms", DCTERMS)
    g.bind("foaf", FOAF)
    g.bind("rdfs", RDFS)

    paper_uri = PG[f"paper/{paper_id}"]
    g.add((paper_uri, RDF.type, SCHEMA.ScholarlyArticle))
    g.add((paper_uri, DCTERMS.title, Literal(entities.title)))
    if entities.abstract:
        g.add((paper_uri, DCTERMS.abstract, Literal(entities.abstract)))

    def add_entity(collection: str, rdf_type: URIRef, predicate: URIRef, label: str):
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
        g.add((paper_uri, SCHEMA.keywords, Literal(keyword)))

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
