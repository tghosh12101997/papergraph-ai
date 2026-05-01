import re
from collections import Counter
from typing import List, Optional
from app.models.schemas import EntityExtraction

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None


METHOD_TERMS = [
    "knowledge graph", "ontology", "rdf", "sparql", "linked data",
    "transformer", "self-attention", "attention mechanism", "scaled dot-product attention",
    "multi-head attention", "positional encoding", "encoder-decoder", "feed-forward network",
    "bert", "gpt", "llm", "large language model", "convolutional neural network", "cnn",
    "recurrent neural network", "rnn", "long short-term memory", "lstm", "gated recurrent", "gru",
    "graph neural network", "gnn", "random forest", "support vector machine", "svm",
    "logistic regression", "xgboost", "named entity recognition", "entity linking",
    "information extraction", "retrieval augmented generation", "rag", "semantic search",
    "topic modeling", "classification", "clustering", "machine learning", "deep learning",
    "natural language processing", "nlp", "collaborative filtering", "content-based filtering",
    "utility-based recommendation", "multi-attribute utility", "knn", "k-nearest neighbors",
    "cosine similarity", "team formation algorithm", "questionnaire", "big five questionnaire",
]

MODEL_PATTERNS = [
    r"\bTransformer(?:\s+(?:base|big))?\b",
    r"\bSelf[- ]Attention\b",
    r"\bMulti[- ]Head Attention\b",
    r"\bScaled Dot[- ]Product Attention\b",
    r"\bBERT\b", r"\bBioBERT\b", r"\bSciBERT\b", r"\bRoBERTa\b", r"\bGPT[- ]?\d*\b",
    r"\bLLaMA\b", r"\bMistral\b", r"\bT5\b", r"\bResNet\b", r"\bU-Net\b",
    r"\bCNN\b", r"\bRNN\b", r"\bLSTM\b", r"\bGRU\b", r"\bGNN\b",
    r"\bXGBoost\b", r"\bRandom Forest\b", r"\bByteNet\b", r"\bConvS2S\b", r"\bGNMT\b",
    r"\bBig Five Personality Model\b", r"\bCollaborative Filtering Recommender\b",
    r"\bUtility[- ]Based Recommender\b", r"\bKNN\b", r"\bK-Nearest Neighbo[u]?rs\b",
]

DATASET_PATTERNS = [
    r"\bWMT\s*2014\s*English[- ](?:to[- ])?German\b",
    r"\bWMT\s*2014\s*English[- ](?:to[- ])?French\b",
    r"\bWall Street Journal\b", r"\bPenn Treebank\b", r"\bWSJ\b", r"\bBerkeleyParser corpora\b",
    r"\b[A-Z][A-Za-z0-9_-]+\s+(?:dataset|corpus|benchmark|data)\b",
    r"\b(MNIST|CIFAR-10|CIFAR-100|ImageNet|PubMed|SQuAD|CoNLL|MIMIC-III|MIMIC-IV|UMLS|SNOMED CT|OMIM|DBpedia|Wikidata)\b",
    r"\bQuestionnaire Responses\b", r"\bStudent Personality Profiles\b", r"\bAcademic Scores\b", r"\bStudent Trait Scores\b",
]

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "using", "into", "paper", "study",
    "results", "method", "methods", "data", "model", "models", "based", "analysis", "approach",
    "system", "research", "also", "were", "been", "their", "which", "these", "those", "there",
    "where", "when", "than", "such", "page", "best", "while", "will", "show", "shows", "work",
    "used", "over", "under", "more", "less", "other", "because", "through", "within", "between",
    "provided", "proper", "attribution", "google", "permission", "conference", "authorized", "licensed",
}

BAD_TITLE_PARTS = [
    "provided proper attribution", "google hereby", "permission to reproduce", "abstract", "keywords",
    "index terms", "introduction", "doi", "arxiv", "received", "accepted", "published", "copyright",
    "authorized licensed use", "conference on", "proceedings", "ieee", "acm", "springer", "elsevier",
    "university", "department", "faculty", "fakultat", "institute", "school", "laboratory", "email",
    "@", "www.", "http", "https", "downloaded on", "restrictions apply", "journalistic", "scholarly works",
]

AFFILIATION_WORDS = [
    "university", "google", "brain", "research", "department", "faculty", "fakultat", "informatik",
    "institute", "laboratory", "school", "college", "center", "centre", "germany", "usa", "canada",
]


def _load_spacy():
    if spacy is None:
        return None
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


NLP = _load_spacy()


def normalize_text(text: str) -> str:
    replacements = {
        "\u000c": "\n",
        "￾": "-",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "–": "-",
        "—": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def clean_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"--- Page \d+ ---", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_lines(text: str) -> List[str]:
    text = normalize_text(text)
    raw_lines = [line.strip() for line in text.splitlines()]
    lines = []
    for line in raw_lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line.startswith("--- Page"):
            continue
        lines.append(line)
    return lines


def _is_bad_title_line(line: str) -> bool:
    lower = line.lower()
    if any(bad in lower for bad in BAD_TITLE_PARTS):
        return True
    if len(line) < 8 or len(line) > 170:
        return True
    if re.search(r"\S+@\S+", line):
        return True
    letters = sum(ch.isalpha() for ch in line)
    if letters < 6:
        return True
    return False


def _looks_like_person_name(line: str) -> bool:
    cleaned = re.sub(r"[∗*†‡§,;]|\d", " ", line).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    lower = cleaned.lower()
    if not cleaned or any(word in lower for word in AFFILIATION_WORDS):
        return False
    if "@" in cleaned or len(cleaned) > 80:
        return False
    parts = cleaned.split()
    if not (2 <= len(parts) <= 4):
        return False
    return all(re.match(r"^[A-ZÀ-ÖØ-ÞŁ][A-Za-zÀ-ÖØ-öø-ÿŁł.'-]*\.?$", p) for p in parts)


def _join_wrapped_title(lines: List[str], start: int) -> str:
    title_parts = [lines[start]]
    for nxt in lines[start + 1:start + 4]:
        if _is_bad_title_line(nxt) or _looks_like_person_name(nxt):
            break
        low = nxt.lower()
        if any(w in low for w in AFFILIATION_WORDS):
            break
        if re.search(r"\S+@\S+", nxt):
            break
        if len(nxt) <= 90 and not nxt.endswith("."):
            title_parts.append(nxt)
        else:
            break
    return " ".join(title_parts).strip()


def extract_title(text: str) -> str:
    lines = get_lines(text)
    if not lines:
        return "Unknown Title"

    try:
        abstract_idx = next(i for i, line in enumerate(lines[:120]) if line.lower().startswith("abstract"))
    except StopIteration:
        abstract_idx = min(len(lines), 80)

    candidates = []
    for i, line in enumerate(lines[:abstract_idx]):
        if _is_bad_title_line(line) or _looks_like_person_name(line):
            continue
        joined = _join_wrapped_title(lines, i)
        lower = joined.lower()
        score = 0
        word_count = len(joined.split())
        if 3 <= word_count <= 16:
            score += 3
        if any(term in lower for term in [
            "attention", "transformer", "knowledge graph", "recommendation", "system", "strategy",
            "architecture", "model", "method", "towards", "toward", "learning", "network",
        ]):
            score += 4
        if i < 25:
            score += 1
        if joined.endswith(".") or joined.endswith(":"):
            score -= 2
        candidates.append((score, joined, i))

    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[2]))
        return candidates[0][1]

    for line in lines[:60]:
        if not _is_bad_title_line(line) and not _looks_like_person_name(line):
            return line
    return "Unknown Title"


def extract_abstract(text: str) -> Optional[str]:
    text = normalize_text(text)
    match = re.search(
        r"\babstract\b\s*[-—:]?\s*(.*?)(?:\n\s*(?:index terms|keywords)\b|\n\s*1\.?\s*introduction\b|\n\s*I\.\s*INTRODUCTION\b|\n\s*introduction\b)",
        text,
        re.I | re.S,
    )
    if not match:
        return None
    abstract = clean_text(match.group(1))
    abstract = re.split(r"\bEqual contribution\b|\bWork performed while\b|\b31st Conference\b", abstract, flags=re.I)[0]
    return abstract[:2500].strip() or None


def extract_authors(text: str, title: str) -> List[str]:
    lines = get_lines(text)
    authors = []

    try:
        abstract_idx = next(i for i, line in enumerate(lines[:160]) if line.lower().startswith("abstract"))
    except StopIteration:
        abstract_idx = min(len(lines), 80)

    title_idx = None
    for i, line in enumerate(lines[:abstract_idx]):
        if clean_text(line).lower() == clean_text(title).lower():
            title_idx = i
            break

    search_start = 0 if title_idx is None else max(0, title_idx + 1)
    search_lines = lines[search_start:abstract_idx]

    for line in search_lines:
        if line == title or _is_bad_title_line(line) and not _looks_like_person_name(line):
            continue
        segments = re.split(r"\s{2,}|,| and ", line)
        for segment in segments:
            segment = re.sub(r"[∗*†‡§]+", " ", segment)
            segment = re.sub(r"\([^)]*\)", " ", segment)
            segment = re.sub(r"\s+", " ", segment).strip()
            if _looks_like_person_name(segment):
                authors.append(segment)

    if NLP and len(authors) < 2:
        possible = " ".join(search_lines)
        possible = re.sub(r"\S+@\S+", " ", possible)
        doc = NLP(possible)
        for ent in doc.ents:
            if ent.label_ == "PERSON" and _looks_like_person_name(ent.text):
                authors.append(ent.text.strip())

    cleaned = []
    seen = set()
    for name in authors:
        name = re.sub(r"\s+", " ", name).strip(" .,-")
        key = name.lower()
        if key not in seen and name.lower() != title.lower():
            seen.add(key)
            cleaned.append(name)
    return cleaned[:15]


def extract_terms_from_list(text: str, terms: List[str]) -> List[str]:
    found = []
    lower = text.lower()
    for term in terms:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", lower):
            if term.isupper() or len(term) <= 4:
                found.append(term.upper())
            else:
                found.append(term.title())
    return sorted(set(found), key=str.lower)


def extract_models(text: str) -> List[str]:
    found = []
    for pattern in MODEL_PATTERNS:
        found.extend(re.findall(pattern, text, flags=re.I))
    cleaned = []
    for x in found:
        if isinstance(x, tuple):
            x = " ".join([p for p in x if p])
        x = re.sub(r"\s+", " ", str(x)).strip(" ,.;:")
        if len(x) > 1:
            cleaned.append(x)
    return sorted(set(cleaned), key=str.lower)[:30]


def extract_datasets(text: str) -> List[str]:
    found = []
    for pattern in DATASET_PATTERNS:
        matches = re.findall(pattern, text, flags=re.I)
        for m in matches:
            if isinstance(m, tuple):
                found.append(" ".join([part for part in m if part]).strip())
            else:
                found.append(m.strip())

    normalized = clean_text(text)
    if re.search(r"WMT\s*2014.*English[- ]to[- ]German|English[- ]German", normalized, re.I):
        found.append("WMT 2014 English-German")
    if re.search(r"WMT\s*2014.*English[- ]to[- ]French|English[- ]French", normalized, re.I):
        found.append("WMT 2014 English-French")
    if re.search(r"questionnaire responses|student responses", normalized, re.I):
        found.append("Questionnaire Responses")
    if re.search(r"personality profile", normalized, re.I):
        found.append("Student Personality Profiles")
    if re.search(r"academic score", normalized, re.I):
        found.append("Academic Scores")

    cleaned = []
    seen = set()
    for item in found:
        item = re.sub(r"\s+", " ", item).strip(" ,.;:")
        if len(item) > 2 and item.lower() not in seen:
            seen.add(item.lower())
            cleaned.append(item)
    return sorted(cleaned, key=str.lower)[:30]


def extract_keywords(text: str, abstract: Optional[str]) -> List[str]:
    keyword_match = re.search(
        r"(?:keywords|index terms)\s*[-—:]?\s*(.*?)(?:\n\s*1\.?\s*introduction|\n\s*I\.\s*INTRODUCTION|\n\s*introduction|\n\s*[A-Z][A-Z\s]{4,}\n)",
        text,
        re.I | re.S,
    )
    if keyword_match:
        raw = clean_text(keyword_match.group(1))
        raw = re.split(r"\bI\.\s*INTRODUCTION\b|\b1\.?\s*Introduction\b", raw, flags=re.I)[0]
        parts = re.split(r"[,;|]", raw)
        keywords = []
        for p in parts:
            p = p.strip().strip(".-")
            if 2 < len(p) < 70 and not any(bad in p.lower() for bad in BAD_TITLE_PARTS):
                keywords.append(p)
        if keywords:
            return sorted(set(keywords), key=str.lower)[:20]

    source = abstract or text[:6000]
    phrase_candidates = []
    for phrase in METHOD_TERMS:
        if re.search(r"\b" + re.escape(phrase) + r"\b", source, re.I):
            phrase_candidates.append(phrase.title() if len(phrase) > 4 else phrase.upper())

    words = re.findall(r"\b[a-zA-Z][a-zA-Z-]{3,}\b", source.lower())
    words = [w for w in words if w not in STOPWORDS and not w.endswith("ing-")]
    counts = Counter(words)
    singles = [word for word, _ in counts.most_common(20) if word not in STOPWORDS]

    out = []
    for item in phrase_candidates + singles:
        if item.lower() not in {x.lower() for x in out}:
            out.append(item)
    return out[:15]


def extract_topics(keywords: List[str], methods: List[str]) -> List[str]:
    combined = keywords[:8] + methods[:10]
    out = []
    for item in combined:
        value = item.title() if not item.isupper() else item
        if value.lower() not in {x.lower() for x in out}:
            out.append(value)
    return out[:15]


def extract_entities(text: str) -> EntityExtraction:
    text = normalize_text(text)
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