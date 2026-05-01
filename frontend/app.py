import re
import json

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

st.set_page_config(page_title="PaperGraph AI v2", layout="wide")

API_BASE = st.sidebar.text_input("Backend API", value="http://localhost:8000/api")
st.title("PaperGraph AI v2")
st.caption("Research paper → extracted entities → RDF triples → SPARQL → Graph QA")


def api_url(path: str) -> str:
    return f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"

def normalize_paper_id(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        raise ValueError("Paste the generated 8-character paper_id, not the PDF URL. Example: 1194ca51")
    value = value.strip("/ ")
    if "/" in value:
        value = value.split("/")[-1]
    if not re.match(r"^[A-Za-z0-9_-]{4,64}$", value):
        raise ValueError("Invalid paper_id format. Use the ID shown after upload, for example 1194ca51.")
    return value

def get_json(path: str):
    response = requests.get(api_url(path), timeout=60)
    response.raise_for_status()
    return response.json()


def post_json(path: str, payload: dict, timeout: int = 120):
    response = requests.post(api_url(path), json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def put_json(path: str, payload: dict, timeout: int = 120):
    response = requests.put(api_url(path), json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def list_to_text(values):
    return "\n".join(values or [])


def text_to_list(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def compact_uri(uri: str) -> str:
    replacements = {
        "https://example.org/papergraph/": "pg:",
        "https://schema.org/": "schema:",
        "http://purl.org/dc/terms/": "dcterms:",
        "http://xmlns.com/foaf/0.1/": "foaf:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    }
    for base, prefix in replacements.items():
        if uri.startswith(base):
            return uri.replace(base, prefix)
    return uri


def render_graph(triples):
    net = Network(height="650px", width="100%", directed=True, notebook=False)
    net.barnes_hut()
    added = set()

    for t in triples:
        s = compact_uri(t["subject"])
        p = compact_uri(t["predicate"])
        o = compact_uri(t["object"])
        if s not in added:
            net.add_node(s, label=s, title=t["subject"])
            added.add(s)
        if o not in added:
            net.add_node(o, label=o[:80], title=t["object"])
            added.add(o)
        net.add_edge(s, o, label=p.split(":")[-1], title=p)

    html = net.generate_html()
    components.html(html, height=680, scrolling=True)


def show_download_buttons(paper_id):
    cols = st.columns(3)
    for col, fmt in zip(cols, ["ttl", "rdf", "jsonld"]):
        with col:
            url = api_url(f"papers/{paper_id}/export?format={fmt}")
            try:
                content = requests.get(url, timeout=30).content
                st.download_button(
                    label=f"Download {fmt.upper()}",
                    data=content,
                    file_name=f"papergraph_{paper_id}.{fmt}",
                    mime="text/plain",
                )
            except Exception:
                st.warning(f"{fmt.upper()} export not available")


if "paper_id" not in st.session_state:
    st.session_state.paper_id = None
if "paper" not in st.session_state:
    st.session_state.paper = None

with st.sidebar:
    st.header("Status")
    try:
        health = get_json("health")
        st.success(f"Backend: {health['status']} | v{health['version']}")
        st.info(f"LLM enabled: {health['llm_enabled']}")
    except Exception as exc:
        st.error(f"Backend not reachable: {exc}")

    existing_id = st.text_input("Load existing paper_id", placeholder="Example: 1194ca51")
    st.caption("Use the generated paper_id only. Do not paste the PDF URL here.")

    if st.button("Load paper") and existing_id:
        try:
            cleaned_id = normalize_paper_id(existing_id)
            st.session_state.paper = get_json(f"papers/{cleaned_id}")
            st.session_state.paper_id = cleaned_id
            st.success(f"Loaded paper_id: {cleaned_id}")
        except Exception as exc:
            st.error(exc)

upload_tab, correct_tab, graph_tab, sparql_tab, qa_tab, text_tab = st.tabs([
    "1 Upload",
    "2 Correct Entities",
    "3 Graph",
    "4 SPARQL",
    "5 Graph QA",
    "6 Extracted Text",
])

with upload_tab:
    st.subheader("Upload a research paper PDF")
    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
    extractor = st.radio("Extraction mode", ["hybrid", "rule", "llm"], horizontal=True)
    upload_to_fuseki = st.checkbox("Upload graph to Fuseki after extraction", value=False)

    if st.button("Process PDF", type="primary") and uploaded_file:
        try:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            params = {"extractor": extractor, "upload_to_fuseki": str(upload_to_fuseki).lower()}
            with st.spinner("Extracting entities and building RDF graph..."):
                response = requests.post(api_url("upload"), files=files, params=params, timeout=180)
                response.raise_for_status()
            st.session_state.paper = response.json()
            st.session_state.paper_id = st.session_state.paper["paper_id"]
            st.success(f"Created graph for paper_id: {st.session_state.paper_id}")
        except Exception as exc:
            st.error(f"Upload failed: {exc}")

    if st.session_state.paper:
        st.subheader("Extraction result")
        st.json(st.session_state.paper["entities"])
        show_download_buttons(st.session_state.paper_id)

with correct_tab:
    st.subheader("Human correction screen")
    if not st.session_state.paper:
        st.info("Upload or load a paper first.")
    else:
        entities = st.session_state.paper["entities"]
        with st.form("correction_form"):
            title = st.text_input("Title", value=entities.get("title", ""))
            abstract = st.text_area("Abstract", value=entities.get("abstract") or "", height=140)
            col1, col2 = st.columns(2)
            with col1:
                authors = st.text_area("Authors, one per line", value=list_to_text(entities.get("authors")), height=140)
                methods = st.text_area("Methods, one per line", value=list_to_text(entities.get("methods")), height=160)
                datasets = st.text_area("Datasets, one per line", value=list_to_text(entities.get("datasets")), height=140)
            with col2:
                models = st.text_area("Models, one per line", value=list_to_text(entities.get("models")), height=140)
                keywords = st.text_area("Keywords, one per line", value=list_to_text(entities.get("keywords")), height=160)
                topics = st.text_area("Topics, one per line", value=list_to_text(entities.get("topics")), height=140)
            upload_corrected_to_fuseki = st.checkbox("Upload corrected graph to Fuseki", value=False)
            submitted = st.form_submit_button("Save corrections and rebuild RDF", type="primary")

        if submitted:
            payload = {
                "entities": {
                    "title": title,
                    "authors": text_to_list(authors),
                    "methods": text_to_list(methods),
                    "datasets": text_to_list(datasets),
                    "models": text_to_list(models),
                    "keywords": text_to_list(keywords),
                    "topics": text_to_list(topics),
                    "abstract": abstract or None,
                },
                "upload_to_fuseki": upload_corrected_to_fuseki,
            }
            try:
                updated = put_json(f"papers/{st.session_state.paper_id}/entities", payload)
                st.session_state.paper = get_json(f"papers/{st.session_state.paper_id}")
                st.success("Corrections saved and RDF exports regenerated.")
                st.json(updated["entities"])
            except Exception as exc:
                st.error(exc)

with graph_tab:
    st.subheader("Knowledge graph visualization")
    if not st.session_state.paper:
        st.info("Upload or load a paper first.")
    else:
        triples = st.session_state.paper.get("triples", [])
        st.write(f"Triples: {len(triples)}")
        render_graph(triples)
        with st.expander("Triples table"):
            df = pd.DataFrame(triples)
            if not df.empty:
                df = df.applymap(lambda x: compact_uri(str(x)))
            st.dataframe(df, use_container_width=True)

with sparql_tab:
    st.subheader("SPARQL query interface")
    if not st.session_state.paper:
        st.info("Upload or load a paper first.")
    else:
        default_query = """PREFIX pg: <https://example.org/papergraph/>
PREFIX schema: <https://schema.org/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?paperTitle ?methodLabel WHERE {
  ?paper dcterms:title ?paperTitle ;
         pg:usesMethod ?method .
  ?method rdfs:label ?methodLabel .
}
LIMIT 50"""
        question = st.text_input("Optional: generate SPARQL from a question", placeholder="Which methods are used in this paper?")
        if st.button("Generate SPARQL") and question:
            try:
                result = post_json(f"papers/{st.session_state.paper_id}/generate-sparql", {"question": question})
                st.session_state.generated_sparql = result["sparql"]
            except Exception as exc:
                st.error(exc)

        query = st.text_area("SPARQL", value=st.session_state.get("generated_sparql", default_query), height=300)
        if st.button("Run SPARQL", type="primary"):
            try:
                result = post_json(f"papers/{st.session_state.paper_id}/sparql", {"query": query})
                st.success(f"Rows: {result['raw_count']}")
                st.dataframe(pd.DataFrame(result["rows"]), use_container_width=True)
            except Exception as exc:
                st.error(exc)

with qa_tab:
    st.subheader("GraphRAG-style question answering")
    if not st.session_state.paper:
        st.info("Upload or load a paper first.")
    else:
        q = st.text_input("Ask a question", placeholder="What datasets and methods are used in this paper?")
        if st.button("Ask graph", type="primary") and q:
            try:
                result = post_json(f"papers/{st.session_state.paper_id}/qa", {"question": q}, timeout=180)
                st.markdown("### Answer")
                st.write(result["answer"])
                with st.expander("Generated / fallback SPARQL"):
                    st.code(result.get("sparql") or "", language="sparql")
                with st.expander("Evidence from graph"):
                    st.dataframe(pd.DataFrame(result["evidence"]), use_container_width=True)
            except Exception as exc:
                st.error(exc)

with text_tab:
    st.subheader("Extracted PDF text")
    if not st.session_state.paper_id:
        st.info("Upload or load a paper first.")
    else:
        try:
            text = requests.get(api_url(f"papers/{st.session_state.paper_id}/text"), timeout=60).text
            st.text_area("Text", value=text[:30000], height=600)
        except Exception as exc:
            st.error(exc)
