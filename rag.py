import re
from pathlib import Path

KNOWLEDGE_FILE = Path(__file__).with_name("knowledge.txt")


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z]{3,}", text.lower())
        if token not in {"the", "and", "for", "with", "you", "your", "are", "such"}
    }


def _load_chunks() -> list[str]:
    if not KNOWLEDGE_FILE.exists():
        return []
    text = KNOWLEDGE_FILE.read_text(encoding="utf-8")
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    return chunks


def retrieve_context(query: str, k: int = 2) -> str:
    """Return the most relevant local knowledge snippets without external vector dependencies."""
    chunks = _load_chunks()
    if not chunks:
        return ""

    query_tokens = _tokenize(query)
    scored_chunks = []
    for chunk in chunks:
        score = len(query_tokens & _tokenize(chunk))
        scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for score, chunk in scored_chunks[:k] if score > 0]
    if not selected:
        selected = chunks[:k]
    return "\n".join(selected)
