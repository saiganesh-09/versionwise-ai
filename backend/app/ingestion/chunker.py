"""Chunking: parsed blocks -> token-budgeted chunks with metadata.

Rules:
- Paragraphs are never split mid-way unless a single paragraph alone exceeds
  the token budget (then we hard-split on token boundaries).
- Headings start a fresh chunk and become `section_title`.
- Overlap carries the trailing tokens of one chunk into the next so sentences
  spanning the boundary still have context.
"""

import hashlib
from dataclasses import dataclass

import tiktoken

from app.ingestion.parsers import ParsedDocument

_enc = tiktoken.get_encoding("cl100k_base")


def _tokens(text: str) -> list[int]:
    return _enc.encode(text, disallowed_special=())


def _detokens(tokens: list[int]) -> str:
    return _enc.decode(tokens)


@dataclass
class ChunkData:
    chunk_index: int
    content: str
    page_number: int | None
    section_title: str | None
    token_count: int
    content_hash: str


def _split_paragraph_tokens(text: str, budget: int) -> list[list[int]]:
    """Hard-split an over-budget paragraph on token boundaries."""
    toks = _tokens(text)
    return [toks[i : i + budget] for i in range(0, len(toks), budget)]


def chunk_document(
    parsed: ParsedDocument, *, max_tokens: int = 512, overlap_tokens: int = 64
) -> list[ChunkData]:
    chunks: list[ChunkData] = []

    def emit(content: str, page: int | None, section: str | None) -> None:
        content = content.strip()
        if not content:
            return
        chunks.append(
            ChunkData(
                chunk_index=len(chunks),
                content=content,
                page_number=page,
                section_title=section,
                token_count=len(_tokens(content)),
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
            )
        )

    for block in parsed.blocks:
        paragraphs = [p for p in block.text.split("\n") if p.strip()]
        # Re-join real paragraph breaks (blocks already carry paragraph text).
        buf: list[str] = []
        buf_tokens = 0
        carry: list[int] = []

        for para in paragraphs:
            para = para.strip()
            para_toks = _tokens(para)

            # Oversized single paragraph: flush buf, hard-split, continue.
            if len(para_toks) > max_tokens:
                if buf:
                    emit("\n\n".join(buf), block.page_number, block.section_title)
                    carry = _tokens(buf[-1])[:overlap_tokens]
                    buf, buf_tokens = [], 0
                pieces = _split_paragraph_tokens(para, max_tokens)
                for piece in pieces[:-1]:
                    emit(_detokens(piece), block.page_number, block.section_title)
                # Last piece continues into the buffer for overlap continuity.
                tail_text = _detokens(pieces[-1])
                buf = [_detokens(carry)] if carry else []
                buf.append(tail_text)
                buf_tokens = sum(len(_tokens(b)) for b in buf)
                continue

            if buf_tokens + len(para_toks) > max_tokens and buf:
                emit("\n\n".join(buf), block.page_number, block.section_title)
                carry = _tokens(buf[-1])[:overlap_tokens]
                buf = ([_detokens(carry)] if carry else []) + [para]
                buf_tokens = len(_tokens("\n\n".join(buf)))
            else:
                buf.append(para)
                buf_tokens += len(para_toks) + 2  # account for \n\n join roughly

        if buf:
            emit("\n\n".join(buf), block.page_number, block.section_title)

    return chunks
