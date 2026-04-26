import os
import re
from pathlib import Path
from typing import Optional

KNOWLEDGE_FILE = Path(__file__).with_name("knowledge.txt")
SIMILARITY_THRESHOLD = 0.75

_vector_store = None
_store_initialized = False


def _load_sections() -> list[str]:
    if not KNOWLEDGE_FILE.exists():
        return []
    text = KNOWLEDGE_FILE.read_text(encoding="utf-8")
    # Split on # SECTION: headers, keeping each full section together
    parts = re.split(r"\n(?=# SECTION:)", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _build_vector_store():
    global _vector_store, _store_initialized
    if _store_initialized:
        return _vector_store

    try:
        from langchain_community.vectorstores import FAISS
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            _store_initialized = True
            return None

        sections = _load_sections()
        if not sections:
            _store_initialized = True
            return None

        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=api_key,
        )
        _vector_store = FAISS.from_texts(sections, embeddings)
    except Exception:
        pass

    _store_initialized = True
    return _vector_store


def retrieve_context(query: str, k: int = 2) -> str:
    """Return relevant knowledge snippets using FAISS similarity search.

    Converts L2 distance to cosine similarity (valid for unit-norm embeddings):
        cos_sim = 1 - (l2_dist^2 / 2)
    Returns empty string when no chunk reaches SIMILARITY_THRESHOLD.
    Falls back to token matching when FAISS is unavailable.
    """
    store = _build_vector_store()

    if store is not None:
        try:
            results = store.similarity_search_with_score(query, k=k)
            selected = []
            for doc, l2_dist in results:
                cos_sim = max(0.0, 1.0 - (l2_dist ** 2) / 2.0)
                if cos_sim >= SIMILARITY_THRESHOLD:
                    selected.append(doc.page_content)
            return "\n\n".join(selected)
        except Exception:
            pass

    return _token_retrieve(query, k)


# ── Token-matching fallback (no external deps) ────────────────────────────────

_STOPWORDS = {"the", "and", "for", "with", "you", "your", "are", "such", "that", "this"}


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z]{3,}", text.lower()) if t not in _STOPWORDS}


def _token_retrieve(query: str, k: int = 2) -> str:
    sections = _load_sections()
    if not sections:
        return ""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return ""
    scored = sorted(
        ((len(query_tokens & _tokenize(s)), s) for s in sections),
        reverse=True,
    )
    selected = [s for score, s in scored[:k] if score >= 1]
    return "\n\n".join(selected)
