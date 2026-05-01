import json
from pathlib import Path
import tempfile
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="PaperGraph AI", layout="wide")

st.title("PaperGraph AI")
st.caption("Upload a research paper and convert it into a Knowledge Graph with RDF triples.")


def shorten_uri(value: str) -> str:
    replacements = {
        "https://example.org/papergraph/": "pg:",
        "https://schema.org/": "schema:",
        "http://purl.org/dc/terms/": "dcterms:",
        "http://xmlns.com/foaf/0.1/": "foaf:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    }
    for long, short in replacements.items():
        value = value.replace(long, short)
    return value


def render_graph(triples):
    net = Network(height="650px", width="100%", directed=True, bgcolor="#ffffff", font_color="#222222")
    net.barnes_hut(gravity=-2500, central_gravity=0.25, spring_length=180, spring_strength=0.04)

    added_nodes = set()
    for triple in triples:
        s = shorten_uri(triple["subject"])
        p = shorten_uri(triple["predicate"])
        o = shorten_uri(triple["object"])

        for node in [s, o]:
            if node not in added_nodes:
                shape = "box" if node.startswith("pg:paper") else "dot"
                net.add_node(node, label=node, title=node, shape=shape)
                added_nodes.add(node)
        net.add_edge(s, o, label=p.split(":")[-1], title=p)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        html = Path(tmp.name).read_text(encoding="utf-8")
    components.html(html, height=680, scrolling=True)


with st.sidebar:
    st.header("Backend")
    api_base = st.text_input("API Base URL", value=API_BASE)
    if st.button("Check API health"):
        try:
            health = requests.get(f"{api_base}/health", timeout=10).json()
            st.success(health)
        except Exception as exc:
            st.error(f"API not reachable: {exc}")

uploaded_file = st.file_uploader("Upload a research paper PDF", type=["pdf"])

if uploaded_file:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info(f"Selected file: {uploaded_file.name}")
        process = st.button("Build Knowledge Graph", type="primary")

    if process:
        with st.spinner("Extracting text, entities, RDF triples, and graph exports..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            response = requests.post(f"{api_base}/upload", files=files, timeout=120)

        if response.status_code != 200:
            st.error(response.text)
        else:
            result = response.json()
            st.session_state["result"] = result

if "result" in st.session_state:
    result = st.session_state["result"]
    paper_id = result["paper_id"]
    entities = result["entities"]
    triples = result["triples"]

    st.success(f"Knowledge Graph created. Paper ID: {paper_id}")

    tab1, tab2, tab3, tab4 = st.tabs(["Extracted Entities", "Graph Visualization", "RDF Triples", "Exports"])

    with tab1:
        st.subheader(entities.get("title", "Unknown Title"))
        if entities.get("abstract"):
            with st.expander("Abstract"):
                st.write(entities["abstract"])

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### Authors")
            st.write(entities.get("authors") or ["No authors detected"])
            st.markdown("### Datasets")
            st.write(entities.get("datasets") or ["No datasets detected"])
        with c2:
            st.markdown("### Methods")
            st.write(entities.get("methods") or ["No methods detected"])
            st.markdown("### Models")
            st.write(entities.get("models") or ["No models detected"])
        with c3:
            st.markdown("### Keywords")
            st.write(entities.get("keywords") or ["No keywords detected"])
            st.markdown("### Topics")
            st.write(entities.get("topics") or ["No topics detected"])

    with tab2:
        render_graph(triples)

    with tab3:
        df = pd.DataFrame(triples)
        df = df.applymap(shorten_uri)
        st.dataframe(df, use_container_width=True, height=500)

    with tab4:
        st.markdown("Download RDF exports from the backend:")
        for fmt in ["ttl", "rdf", "jsonld"]:
            url = f"{api_base}/papers/{paper_id}/export?format={fmt}"
            try:
                export_response = requests.get(url, timeout=20)
                export_response.raise_for_status()
                st.download_button(
                    label=f"Download {fmt.upper()}",
                    data=export_response.content,
                    file_name=f"papergraph_{paper_id}.{fmt}",
                    mime=export_response.headers.get("content-type", "text/plain"),
                )
            except Exception as exc:
                st.warning(f"Could not prepare {fmt} export: {exc}")

        with st.expander("Raw API result"):
            st.json(result)
else:
    st.markdown("""
    ### What this MVP does
    - Extracts text from PDF research papers
    - Detects title, authors, methods, datasets, models, keywords, and topics
    - Builds RDF triples using RDFLib
    - Exports Turtle, RDF/XML, and JSON-LD
    - Visualizes the Knowledge Graph interactively
    """)
