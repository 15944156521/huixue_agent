import re
from pathlib import Path
from typing import List, Optional

from rag.bm25 import SimpleBM25


def _tokenize(text: str) -> List[str]:
    """
    中英文混合分词：保留连续片段，并对含中文的片段拆成单字，
    避免「操作系统学习要点」整段作为一个 token 导致查询词无法命中。
    """
    tokens: List[str] = []
    for seg in re.findall(r"[\w\u4e00-\u9fff]+", (text or "").lower()):
        tokens.append(seg)
        if re.search(r"[\u4e00-\u9fff]", seg):
            tokens.extend(list(seg))
    return tokens


class KnowledgeRetriever:
    """
    轻量 RAG：从 data/knowledge 下加载 .md/.txt，按段落分块，BM25 检索。
    不依赖向量模型与外部 embedding，便于课程项目部署与调试。
    """

    def __init__(self, knowledge_dir=None):
        base = Path(__file__).resolve().parent.parent
        self.knowledge_dir = Path(knowledge_dir or base / "data" / "knowledge")
        self._chunks: List[str] = []
        self._bm25: Optional[SimpleBM25] = None
        self._load_corpus()

    def _load_corpus(self):
        self._chunks = []
        if not self.knowledge_dir.is_dir():
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            self._bm25 = None
            return

        for path in sorted(self.knowledge_dir.rglob("*")):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for block in re.split(r"\n\s*\n", text.strip()):
                block = block.strip()
                if len(block) < 20:
                    continue
                self._chunks.append(block)

        aligned_chunks: List[str] = []
        tokenized: List[List[str]] = []
        for chunk in self._chunks:
            tokens = _tokenize(chunk)
            if tokens:
                aligned_chunks.append(chunk)
                tokenized.append(tokens)
        self._chunks = aligned_chunks

        if tokenized:
            self._bm25 = SimpleBM25(tokenized)
        else:
            self._bm25 = None

    def reload(self):
        self._load_corpus()

    def retrieve(self, query: str, top_k: int = 4) -> str:
        if not query or not self._chunks or not self._bm25:
            return ""
        q_tokens = _tokenize(query)
        if not q_tokens:
            return ""
        scores = self._bm25.get_scores(q_tokens)
        if not scores:
            return ""
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        parts = []
        for idx in ranked:
            if scores[idx] <= 0:
                continue
            snippet = self._chunks[idx].strip()
            if len(snippet) > 800:
                snippet = snippet[:800] + "…"
            parts.append(snippet)
        return "\n\n---\n\n".join(parts)

    def chunk_count(self) -> int:
        return len(self._chunks)
