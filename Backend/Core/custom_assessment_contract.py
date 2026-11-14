"""Bind a proposed custom format to the private evidence a user reviewed."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from Backend.Core.custom_assessment_evidence import (
    MAX_PAGES_PER_SOURCE,
    MAX_SOURCES,
    LocalDocumentEvidence,
)

_Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
_Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
_Format = Literal["multiple-choice", "short-answer", "written", "essay"]


class PageCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_sha256: _Digest
    page: int = Field(strict=True, ge=1, le=MAX_PAGES_PER_SOURCE)


class DraftSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,39}$")]
    title: _Title
    question_count: int = Field(strict=True, ge=1, le=250)
    answer_count: int = Field(strict=True, ge=1, le=250)
    candidate_marks: int | None = Field(default=None, strict=True, ge=1, le=1000)
    formats: tuple[_Format, ...] = Field(min_length=1, max_length=4)
    sources: tuple[PageCitation, ...] = Field(min_length=1, max_length=96)

    @model_validator(mode="after")
    def validate_counts(self) -> DraftSection:
        if self.answer_count > self.question_count:
            raise ValueError("Answer count exceeds available questions")
        if len(self.formats) != len(set(self.formats)):
            raise ValueError("Question formats must be distinct")
        if len(self.sources) != len(set(self.sources)):
            raise ValueError("Page citations must be distinct")
        return self


@dataclass(frozen=True)
class CustomFormatDraft:
    name: str
    duration_minutes: int | None
    sections: tuple[DraftSection, ...]
    evidence_ids: tuple[tuple[str, str], ...]

    @property
    def candidate_marks(self) -> int | None:
        marks = [section.candidate_marks for section in self.sections]
        if any(value is None for value in marks):
            return None
        return sum(value for value in marks if value is not None)

    @property
    def digest(self) -> str:
        payload = {
            "version": 1,
            "name": self.name,
            "duration_minutes": self.duration_minutes,
            "sections": [section.model_dump(mode="json") for section in self.sections],
            "evidence": self.evidence_ids,
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class ConfirmedCustomFormat:
    draft: CustomFormatDraft


def review_custom_format(
    name: str,
    evidence: Sequence[LocalDocumentEvidence],
    sections: Sequence[DraftSection],
    *,
    duration_minutes: int | None = None,
) -> CustomFormatDraft:
    """Create a reviewable proposal; evidence coverage does not prove correctness."""
    name = name.strip()
    if not name or len(name) > 120:
        raise ValueError("Enter a name of 1 to 120 characters")
    if duration_minutes is not None and (
        type(duration_minutes) is not int or not 1 <= duration_minutes <= 600
    ):
        raise ValueError("Enter a duration of 1 to 600 minutes or leave it blank")
    if not 1 <= len(sections) <= 20:
        raise ValueError("Provide between one and twenty sections")
    if len({section.id for section in sections}) != len(sections):
        raise ValueError("Section identifiers must be distinct")
    by_digest = {doc.sha256: doc for doc in evidence}
    if len(by_digest) != len(evidence) or len(evidence) > MAX_SOURCES:
        raise ValueError("Invalid custom source set")
    papers = {doc.sha256 for doc in evidence if doc.role == "question-paper"}
    if len(papers) < 3:
        raise ValueError("Provide at least three distinct question papers")
    readable = {
        (doc.sha256, page.number)
        for doc in evidence
        for page in doc.pages
        if page.text.strip()
    }
    normalized = []
    for section in sections:
        sources = tuple(
            sorted(
                section.sources,
                key=lambda source: (source.document_sha256, source.page),
            )
        )
        if any(
            (source.document_sha256, source.page) not in readable for source in sources
        ):
            raise ValueError("Every citation must resolve to a readable page")
        if not papers.issubset(source.document_sha256 for source in sources):
            raise ValueError("Each section must cite every question paper")
        normalized.append(section.model_copy(update={"sources": sources}))
    return CustomFormatDraft(
        name,
        duration_minutes,
        tuple(normalized),
        tuple(sorted((doc.role, doc.sha256) for doc in evidence)),
    )


def confirm_custom_format(
    draft: CustomFormatDraft, *, reviewed_digest: str
) -> ConfirmedCustomFormat:
    """Reject confirmation of a draft that differs from the one displayed."""
    if reviewed_digest != draft.digest:
        raise ValueError("The assessment format changed. Review it again.")
    return ConfirmedCustomFormat(draft)
