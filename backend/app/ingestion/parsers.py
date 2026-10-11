"""Document parsers: bytes -> structured text with page/section metadata.

Supported: .txt, .docx, .pdf. Everything else is rejected before parsing.
A PDF whose pages yield no extractable text is treated as a scanned document —
we fail loudly saying OCR is required rather than indexing silence.
"""

import io
import re
from dataclasses import dataclass, field

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf"}

# File-type sniffing: extension can lie, magic bytes mostly can't.
_MAGIC = {
    ".pdf": [b"%PDF-"],
    ".docx": [b"PK\x03\x04"],  # zip container
}


class ParseError(Exception):
    """User-facing parse failure (corrupt file, wrong format, etc.)."""


class ScannedPdfError(ParseError):
    """PDF has no extractable text — needs OCR we don't implement yet."""


@dataclass
class ParsedBlock:
    """A heading-delimited block of text within one page."""

    text: str
    page_number: int | None  # 1-based; None when the format has no pages
    section_title: str | None = None


@dataclass
class ParsedDocument:
    blocks: list[ParsedBlock] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(len(b.text) for b in self.blocks)


def detect_format(filename: str, data: bytes) -> str:
    """Validate extension AND magic bytes. Returns '.pdf' | '.docx' | '.txt'."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise ParseError(
            f"Unsupported file type {ext or '(none)'}. Supported: PDF, DOCX, TXT."
        )
    magics = _MAGIC.get(ext)
    if magics and not any(data.startswith(m) for m in magics):
        raise ParseError(
            f"File extension says {ext} but the content does not match that format."
        )
    if ext == ".txt":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError("File is named .txt but is not valid UTF-8 text.") from exc
    return ext


def _emit_blocks_from_paragraphs(
    paragraphs: list[tuple[str | None, str]], page_number: int | None
) -> list[ParsedBlock]:
    """Group consecutive paragraphs under their nearest heading."""
    blocks: list[ParsedBlock] = []
    current_title: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if buf:
            blocks.append(
                ParsedBlock("\n\n".join(buf).strip(), page_number, current_title)
            )
            buf.clear()

    for style, text in paragraphs:
        if style is not None:  # heading boundary
            flush()
            current_title = text.strip() or None
            continue
        if text.strip():
            buf.append(text.strip())
    flush()
    return blocks


def _parse_txt(data: bytes) -> ParsedDocument:
    text = data.decode("utf-8")
    # Split on blank lines into paragraph blocks; no headings/pages in TXT.
    blocks = [
        ParsedBlock(p.strip(), page_number=None)
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]
    return ParsedDocument(blocks)


_HEADING_STYLE = re.compile(r"^Heading\s+(\d+)", re.IGNORECASE)


def _parse_docx(data: bytes) -> ParsedDocument:
    import docx

    try:
        doc = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError("Could not read DOCX — file may be corrupt.") from exc
    # DOCX page numbers are render-dependent — we keep heading structure
    # instead and leave page_number None rather than fabricating it.
    paragraphs = [
        (p.style.name, p.text) if p.style and _HEADING_STYLE.match(p.style.name)
        else (None, p.text)
        for p in doc.paragraphs
        if p.text.strip()
    ]
    return ParsedDocument(_emit_blocks_from_paragraphs(paragraphs, page_number=None))


def _parse_pdf(data: bytes) -> ParsedDocument:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ParseError("Could not read PDF — file may be corrupt.") from exc
    if len(reader.pages) == 0:
        raise ParseError("PDF contains no pages.")

    doc = ParsedDocument()
    extracted_any = False
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            extracted_any = True
            # Paragraph-split inside the page, keeping the page number.
            for para in re.split(r"\n\s*\n|\n(?=\S)", text):
                if para.strip():
                    doc.blocks.append(ParsedBlock(para.strip(), page_number=i))
    if not extracted_any:
        raise ScannedPdfError(
            "No extractable text found — this looks like a scanned PDF and "
            "requires OCR, which is not supported yet."
        )
    return doc


def parse_document(filename: str, data: bytes) -> ParsedDocument:
    fmt = detect_format(filename, data)
    parser = {".txt": _parse_txt, ".docx": _parse_docx, ".pdf": _parse_pdf}[fmt]
    parsed = parser(data)
    if parsed.total_chars == 0:
        raise ParseError("The file contains no extractable text.")
    return parsed
