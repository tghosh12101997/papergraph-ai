from rdflib import Graph
import requests
from app.core.config import settings


def upload_graph_to_fuseki(graph: Graph) -> bool:
    """Optional upload to Apache Jena Fuseki using Graph Store Protocol.

    Requires docker-compose Fuseki service and FUSEKI_ENABLED=true.
    """
    if not settings.fuseki_enabled:
        return False

    endpoint = f"{settings.fuseki_dataset_url}/data?default"
    turtle_data = graph.serialize(format="turtle")
    response = requests.put(
        endpoint,
        data=turtle_data.encode("utf-8"),
        headers={"Content-Type": "text/turtle"},
        timeout=15,
    )
    response.raise_for_status()
    return True
