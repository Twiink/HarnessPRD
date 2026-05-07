"""轻量本地 RAG 服务 — 为接口文档生成检索团队规范和历史示例"""

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import List


KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "knowledge",
    "api_docs",
)


@dataclass(frozen=True)
class RagChunk:
    source: str
    title: str
    content: str


@dataclass(frozen=True)
class RagHit:
    source: str
    title: str
    score: float
    content: str
    content_preview: str


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokenize(text: str) -> set[str]:
    normalized = _normalize_text(text)
    ascii_tokens = set(re.findall(r"[a-zA-Z0-9_:/.-]{2,}", normalized))
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_bigrams = {cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)}
    return ascii_tokens | cjk_bigrams


def _split_markdown(source: str, content: str) -> List[RagChunk]:
    chunks: List[RagChunk] = []
    current_title = os.path.basename(source)
    current_lines: List[str] = []

    for line in content.splitlines():
        if line.startswith("#") and current_lines:
            chunk_content = "\n".join(current_lines).strip()
            if chunk_content:
                chunks.append(RagChunk(source=source, title=current_title, content=chunk_content))
            current_title = line.lstrip("#").strip() or current_title
            current_lines = [line]
        else:
            if line.startswith("#"):
                current_title = line.lstrip("#").strip() or current_title
            current_lines.append(line)

    chunk_content = "\n".join(current_lines).strip()
    if chunk_content:
        chunks.append(RagChunk(source=source, title=current_title, content=chunk_content))

    return chunks


@lru_cache(maxsize=1)
def _load_chunks() -> List[RagChunk]:
    chunks: List[RagChunk] = []
    if not os.path.isdir(KNOWLEDGE_DIR):
        return chunks

    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not filename.endswith((".md", ".txt")):
            continue
        path = os.path.join(KNOWLEDGE_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception:
            continue
        if content:
            chunks.extend(_split_markdown(filename, content))

    return chunks


def _score_chunk(query_tokens: set[str], query_text: str, chunk: RagChunk) -> float:
    chunk_text = _normalize_text(f"{chunk.title}\n{chunk.content}")
    chunk_tokens = _tokenize(chunk_text)
    if not query_tokens or not chunk_tokens:
        return 0

    overlap = len(query_tokens & chunk_tokens)
    score = overlap / max(len(query_tokens), 1)

    # 团队规范是硬约束，即使关键词不完全匹配也应稳定进入上下文。
    if "guidelines" in chunk.source or "规范" in chunk.title:
        score += 0.18

    important_phrases = [
        "接口",
        "api",
        "鉴权",
        "错误码",
        "分页",
        "生成",
        "文案",
        "任务",
        "复制",
        "历史",
        "收藏",
        "登录",
        "数据库",
    ]
    for phrase in important_phrases:
        if phrase in query_text and phrase in chunk_text:
            score += 0.03

    return score


def _build_preview(content: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", content).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def retrieve_api_docs_hits(query: str, top_k: int = 6) -> List[RagHit]:
    """检索接口文档相关 chunk，返回结构化命中结果"""
    chunks = _load_chunks()
    if not chunks:
        return []

    query_text = _normalize_text(query)
    query_tokens = _tokenize(query_text)
    ranked = sorted(
        ((_score_chunk(query_tokens, query_text, chunk), chunk) for chunk in chunks),
        key=lambda item: item[0],
        reverse=True,
    )
    selected = [chunk for score, chunk in ranked if score > 0][:top_k]
    score_map = {id(chunk): score for score, chunk in ranked}
    if not selected:
        selected = [chunk for _, chunk in ranked[:min(top_k, len(ranked))]]

    return [
        RagHit(
            source=chunk.source,
            title=chunk.title,
            score=round(score_map.get(id(chunk), 0), 4),
            content=chunk.content,
            content_preview=_build_preview(chunk.content),
        )
        for chunk in selected
    ]


def format_api_docs_rag_context(hits: List[RagHit]) -> str:
    """把结构化命中结果格式化为可直接注入 prompt 的 Markdown 片段"""
    if not hits:
        return ""

    sections = [
        "以下内容来自本地 RAG 知识库，用于约束接口文档生成。"
        "如果 RAG 内容与当前 PRD 冲突，以当前 PRD 为准；如果只是规范或风格差异，优先遵循 RAG 内容。"
    ]
    for index, hit in enumerate(hits, start=1):
        sections.append(
            f"\n[RAG-{index}] 来源：{hit.source} / {hit.title}\n\n{hit.content}"
        )

    return "\n".join(sections)


def retrieve_api_docs_context(query: str, top_k: int = 6) -> str:
    """检索接口文档相关上下文，返回可直接注入 prompt 的 Markdown 片段"""
    return format_api_docs_rag_context(retrieve_api_docs_hits(query, top_k))
