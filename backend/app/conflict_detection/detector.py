"""Conflict detection: candidate pairs -> LLM classification -> stored findings.

A contradiction is two rules that cannot both hold for the same subject at
overlapping effective times — not merely different wording. Same-document
differences where a newer version takes over later are classified
`updated_by_newer_version` (normal evolution), while overlapping approved
intervals disagreeing on facts are `contradictory`.

Deduping is by unordered chunk pair: re-running detection refreshes open
findings and never reopens a dismissed/resolved one.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import (
    Chunk,
    Conflict,
    ConflictStatus,
    ConflictType,
    Document,
    DocumentPermissionGrant,
    DocumentVersion,
    IngestionStatus,
    User,
    UserRole,
    VersionStatus,
)
from app.services.audit import log_action
from app.services.llm import LLMProvider

logger = logging.getLogger(__name__)

_WORDS = re.compile(r"[a-z0-9]+")
_NUMBERS = re.compile(r"\d+(?:\.\d+)?")
_STOP = {"the", "is", "a", "an", "of", "to", "in", "on", "for", "and", "or",
         "are", "was", "were", "be", "been", "per", "at", "by", "with", "that"}


def _tokens(text: str) -> set[str]:
    return {t for t in _WORDS.findall(text.lower()) if t not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _intervals_overlap(
    a_from: date, a_until: date | None, b_from: date, b_until: date | None
) -> bool:
    a_end = a_until or date.max
    b_end = b_until or date.max
    return a_from < b_end and b_from < a_end


@dataclass
class Candidate:
    chunk_a: Chunk
    chunk_b: Chunk
    version_a: DocumentVersion
    version_b: DocumentVersion
    same_document: bool
    intervals_overlap: bool


def _visible_version_ids(session: Session, user: User) -> list[uuid.UUID]:
    stmt = (
        select(DocumentVersion.id)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(
            DocumentVersion.status.in_(
                [VersionStatus.approved, VersionStatus.superseded]
            ),
            DocumentVersion.ingestion_status == IngestionStatus.completed,
        )
    )
    if user.role != UserRole.admin:
        granted = select(DocumentPermissionGrant.document_id).where(
            DocumentPermissionGrant.user_id == user.id
        )
        stmt = stmt.where(
            # docs the user owns or has any grant on
            (Document.owner_id == user.id) | Document.id.in_(granted)
        )
    return list(session.execute(stmt).scalars())


def candidates(
    session: Session, version_ids: list[uuid.UUID], *, max_pairs: int = 500
) -> list[Candidate]:
    if len(version_ids) < 1:
        return []
    chunks = list(
        session.execute(
            select(Chunk).where(Chunk.version_id.in_(version_ids))
        ).scalars()
    )
    versions = {
        v.id: v
        for v in session.execute(
            select(DocumentVersion).where(DocumentVersion.id.in_(version_ids))
        ).scalars()
    }
    toks = {c.id: _tokens(c.content) for c in chunks}
    out: list[Candidate] = []
    for i, a in enumerate(chunks):
        va = versions[a.version_id]
        for b in chunks[i + 1 :]:
            if b.version_id == a.version_id:
                continue
            vb = versions[b.version_id]
            if _jaccard(toks[a.id], toks[b.id]) < 0.15:
                continue  # unrelated subject matter — not a candidate
            out.append(
                Candidate(
                    chunk_a=a,
                    chunk_b=b,
                    version_a=va,
                    version_b=vb,
                    same_document=va.document_id == vb.document_id,
                    intervals_overlap=_intervals_overlap(
                        va.effective_from, va.effective_until,
                        vb.effective_from, vb.effective_until,
                    ),
                )
            )
            if len(out) >= max_pairs:
                return out
    return out


class _Verdict:
    def __init__(self, type_: ConflictType, confidence: float, explanation: str):
        self.type = type_
        self.confidence = confidence
        self.explanation = explanation


def _classify_rule_based(c: Candidate) -> _Verdict:
    """Deterministic classifier — always runs first; the LLM may refine but a
    hard 'consistent' verdict short-circuits without an API call."""
    ta, tb = c.chunk_a.content, c.chunk_b.content
    if ta.strip().lower() == tb.strip().lower():
        return _Verdict(ConflictType.consistent, 1.0, "Identical text.")

    nums_a, nums_b = set(_NUMBERS.findall(ta)), set(_NUMBERS.findall(tb))
    differing_numbers = nums_a != nums_b
    if not differing_numbers:
        return _Verdict(
            ConflictType.consistent, 0.7,
            "Same numeric assertions; wording differs but no factual clash.",
        )

    if c.same_document and not c.intervals_overlap:
        return _Verdict(
            ConflictType.updated_by_newer_version, 0.9,
            "Same document, non-overlapping intervals with different values — "
            "a legitimate update, not a contradiction.",
        )
    if c.intervals_overlap:
        return _Verdict(
            ConflictType.contradictory, 0.8,
            f"Overlapping effective periods assert different values "
            f"({sorted(nums_a)} vs {sorted(nums_b)}).",
        )
    return _Verdict(
        ConflictType.context_dependent, 0.4,
        "Different values but periods do not overlap; may be intentional.",
    )


def detect_conflicts(
    session: Session,
    user: User,
    *,
    document_id: uuid.UUID | None = None,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
) -> list[Conflict]:
    """Run detection across versions the user can see (or one document's)."""
    settings = settings or get_settings()
    version_ids = _visible_version_ids(session, user)
    if document_id is not None:
        version_ids = [
            vid
            for vid, doc_id in session.execute(
                select(DocumentVersion.id, DocumentVersion.document_id).where(
                    DocumentVersion.id.in_(version_ids)
                )
            )
            if doc_id == document_id
        ]
    cands = candidates(session, version_ids)
    findings: list[Conflict] = []

    for c in cands:
        verdict = _classify_rule_based(c)
        # LLM refinement for borderline cases only — deterministic path stays
        # honest without credentials.
        if llm is not None and verdict.type not in (
            ConflictType.consistent, ConflictType.updated_by_newer_version
        ) and verdict.confidence < 0.85:
            verdict = _classify_llm(llm, c) or verdict
        if verdict.type in (ConflictType.consistent,):
            continue  # not a finding worth storing
        findings.append(_upsert_conflict(session, c, verdict))

    if findings:
        log_action(
            session, actor=user, action="conflicts.detected",
            target_type="conflict",
            detail={"count": len(findings)},
        )
    session.commit()
    return findings


def _classify_llm(llm: LLMProvider, c: Candidate) -> _Verdict | None:
    try:
        raw = llm.complete(
            "You are a conflict classifier for a document-intelligence system. "
            "Decide whether two passages contradict each other for the SAME "
            "subject at overlapping effective times. Respond ONLY with JSON: "
            '{"verdict": one of contradictory|consistent|updated_by_newer_version'
            '|context_dependent|insufficient_evidence, "confidence": 0-1, '
            '"explanation": short string}.',
            json.dumps({
                "task": "conflict_check",
                "same_document": c.same_document,
                "intervals_overlap": c.intervals_overlap,
                "evidence_a": c.chunk_a.content,
                "evidence_b": c.chunk_b.content,
            }),
        )
        data = json.loads(raw)
        return _Verdict(
            ConflictType(data["verdict"]),
            float(data.get("confidence", 0.5)),
            str(data.get("explanation", ""))[:2000],
        )
    except Exception:
        logger.warning("LLM conflict classification failed; using rule verdict")
        return None


def _upsert_conflict(session: Session, c: Candidate, v: _Verdict) -> Conflict:
    """Canonical pair order (lower chunk id = a) — dedupe on re-runs. Open
    findings refresh; dismissed/resolved stay untouched (no endless reopen)."""
    a, b = sorted([c.chunk_a, c.chunk_b], key=lambda x: str(x.id))
    existing = session.execute(
        select(Conflict).where(
            Conflict.chunk_a_id == a.id, Conflict.chunk_b_id == b.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status in (ConflictStatus.potential, ConflictStatus.confirmed):
            existing.conflict_type = v.type
            existing.confidence = v.confidence
            existing.explanation = v.explanation
            session.flush()
        return existing

    row = Conflict(
        document_id=c.version_a.document_id
        if c.same_document
        else None,  # cross-document conflicts have no single owner doc
        chunk_a_id=a.id,
        chunk_b_id=b.id,
        conflict_type=v.type,
        explanation=v.explanation,
        evidence_a=a.content[:4000],
        evidence_b=b.content[:4000],
        confidence=v.confidence,
        status=ConflictStatus.potential,
    )
    session.add(row)
    session.flush()
    return row
