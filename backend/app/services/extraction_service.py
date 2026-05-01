import re
from collections import Counter
from typing import List
from app.models.schemas import EntityExtraction

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None


METHOD_TERMS = [
    "knowledge graph", "ontology", "rdf", "sparql", "linked data",
    "transformer", "bert", "gpt", "llm", "large language model",
    "convolutional neural network", "cnn", "recurrent neural network", "rnn",
    "graph neural network", "gnn", "random forest", "support vector machine",
    "svm", "logistic regression", "xgboost", "named entity recognition",
    "entity linking", "information extraction", "retrieval augmented generation",
    "rag", "semantic search", "topic modeling", "classification", "clustering"
]

MODEL_PATTERNS = [
    r"\bBERT\b", r"\bBioBERT\b", r"\bSciBERT\b", r"\bRoBERTa\b", r"\bGPT[- ]?\d*\b",
    r"\bLLaMA\b", r"\bMistral\b", r"\bT5\b", r"\bResNet\b", r"\bU-Net\b",
    r"\bCNN\b", r"\bRNN\b", r"\bGNN\b", r"\bXGBoost\b"
]

DATASET_PATTERNS = [
    r"\b[A-Z][A-Za-z0-9_-]+\s+dataset\b",
    r"\b[A-Z]{2,}[A-Z0-9_-]*\b(?=\s+(dataset|corpus|benchmark))",
    r"\b(MNIST|CIFAR-10|CIFAR-100|ImageNet|PubMed|SQuAD|CoNLL|MIMIC-III|MIMIC-IV|UMLS|SNOMED CT|OMIM)\b",
]

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "using", "into", "paper",
    "study", "results", "method", "methods", "data", "model", "models", "based",
    "analysis", "approach", "system", "research", "also", "were", "been", "their",
    "which", "these", "those", "there", "where", "when", "than", "such"
}


def _load_spacy():
    if spacy is None:
        return None
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


NLP = _load_spacy()


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = []
    for line in lines[:25]:
        if 8 <= len(line) <= 180:
            lower = line.lower()
            if not any(x in lower for x in ["abstract", "introduction", "keywords", "doi", "arxiv"]):
                candidates.append(line)
    return candidates[0] if candidates else "Unknown Title"


def extract_abstract(text: str) -> str | None:
    match = re.search(r"abstract\s*(.*?)(?:\n\s*keywords|\n\s*1\.?\s*introduction|\n\s*introduction)", text, re.I | re.S)
    if not match:
        return None
    return clean_text(match.group(1))[:2500]


def extract_authors(text: str, title: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    try:
        title_index = lines.index(title)
    except ValueError:
        title_index = 0

    possible = " ".join(lines[title_index + 1:title_index + 6])
    possible = re.sub(r"\d|\*|†|‡|§|,?\s*(University|Institute|Department|Laboratory|School).*", " ", possible, flags=re.I)

    if NLP:
        doc = NLP(possible)
        people = []
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) <= 4:
                people.append(ent.text.strip())
        if people:
            return sorted(set(people))[:12]

    # Fallback: author-like names with initials/capitalized words
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z]+)+\b", possible)
    return sorted(set(names))[:12]


def extract_terms_from_list(text: str, terms: List[str]) -> List[str]:
    found = []
    lower = text.lower()
    for term in terms:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", lower):
            found.append(term.title() if len(term) > 4 else term.upper())
    return sorted(set(found))


def extract_models(text: str) -> List[str]:
    found = []
    for pattern in MODEL_PATTERNS:
        found.extend(re.findall(pattern, text, flags=re.I))
    return sorted(set([x.strip() for x in found if x.strip()]))[:20]


def extract_datasets(text: str) -> List[str]:
    found = []
    for pattern in DATASET_PATTERNS:
        matches = re.findall(pattern, text, flags=re.I)
        for m in matches:
            if isinstance(m, tuple):
                found.append(" ".join([part for part in m if part]).strip())
            else:
                found.append(m.strip())
    cleaned = []
    for item in found:
        item = re.sub(r"\s+", " ", item).strip(" ,.;:")
        if len(item) > 2:
            cleaned.append(item)
    return sorted(set(cleaned))[:20]


def extract_keywords(text: str, abstract: str | None) -> List[str]:
    keyword_match = re.search(r"keywords\s*[:—-]?\s*(.*?)(?:\n\s*1\.?\s*introduction|\n\s*introduction|\n\n)", text, re.I | re.S)
    if keyword_match:
        raw = clean_text(keyword_match.group(1))
        parts = re.split(r"[,;|]", raw)
        keywords = [p.strip().strip(".") for p in parts if 2 < len(p.strip()) < 60]
        if keywords:
            return sorted(set(keywords))[:15]

    source = abstract or text[:5000]
    words = re.findall(r"\b[a-zA-Z][a-zA-Z-]{3,}\b", source.lower())
    words = [w for w in words if w not in STOPWORDS]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(12)]


def extract_topics(keywords: List[str], methods: List[str]) -> List[str]:
    combined = keywords[:8] + methods[:6]
    return sorted(set([x.title() for x in combined]))[:12]


def extract_entities(text: str) -> EntityExtraction:
    title = extract_title(text)
    abstract = extract_abstract(text)
    authors = extract_authors(text, title)
    methods = extract_terms_from_list(text, METHOD_TERMS)
    datasets = extract_datasets(text)
    models = extract_models(text)
    keywords = extract_keywords(text, abstract)
    topics = extract_topics(keywords, methods)

    return EntityExtraction(
        title=title,
        authors=authors,
        methods=methods,
        datasets=datasets,
        models=models,
        keywords=keywords,
        topics=topics,
        abstract=abstract,
    )
