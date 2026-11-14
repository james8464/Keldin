"""Extract private, page-bound evidence without invoking a model or network."""

from __future__ import annotations

import os
import stat
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

import pymupdf

SourceRole = Literal["question-paper", "mark-scheme", "syllabus", "expected-content"]
_ROLES = frozenset({"question-paper", "mark-scheme", "syllabus", "expected-content"})
MAX_SOURCES = 12
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024
MAX_PAGES_PER_SOURCE = 80
MAX_PAGE_CHARACTERS = 40_000
MAX_TOTAL_CHARACTERS = 600_000


@dataclass(frozen=True)
class LocalSource:
    role: SourceRole
    content: bytes


@dataclass(frozen=True)
class LocalPageEvidence:
    number: int
    text: str


@dataclass(frozen=True)
class LocalDocumentEvidence:
    role: SourceRole
    sha256: str
    pages: tuple[LocalPageEvidence, ...]


def inspect_custom_files(
    selections: Sequence[tuple[str, Path]],
) -> tuple[LocalDocumentEvidence, ...]:
    """Read selected local regular files without blocking on special files."""
    if len(selections) > MAX_SOURCES:
        raise ValueError("Too many assessment sources")
    if any(role not in _ROLES for role, _ in selections):
        raise ValueError("Unknown assessment source role")
    if sum(role == "question-paper" for role, _ in selections) < 3:
        raise ValueError("Provide at least three distinct question papers")
    sources = []
    remaining = MAX_TOTAL_BYTES
    for number, (role, path) in enumerate(selections, start=1):
        try:
            with open(path, "rb", opener=_open_source) as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    raise OSError("Not a regular file")
                limit = min(MAX_SOURCE_BYTES, remaining)
                if metadata.st_size > limit:
                    raise ValueError(f"Source {number} exceeds the import size limit")
                content = stream.read(limit + 1)
        except OSError:
            raise ValueError(
                f"Could not read source {number}. Choose the file again."
            ) from None
        if len(content) > limit or len(content) != metadata.st_size:
            raise ValueError(
                f"Source {number} changed during import. Choose the file again."
            )
        sources.append(LocalSource(cast(SourceRole, role), content))
        remaining -= len(content)
    return build_custom_evidence(sources)


def _open_source(filename: str, flags: int) -> int:
    return os.open(filename, flags | os.O_NONBLOCK | os.O_NOFOLLOW)


def _extract_pages(content: bytes, remaining: int) -> tuple[LocalPageEvidence, ...]:
    if not content.startswith(b"%PDF-"):
        raise ValueError("Each source must be a readable PDF")
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("Password-protected PDFs are not supported")
            if document.is_repaired or not document.page_count:
                raise ValueError("Each source must be a readable PDF")
            if document.page_count > MAX_PAGES_PER_SOURCE:
                raise ValueError("A source exceeds the page limit")
            pages = []
            has_visual_content = False
            for number, page in enumerate(document, start=1):
                text = page.get_text("text", sort=True).strip()
                remaining -= len(text)
                if len(text) > MAX_PAGE_CHARACTERS or remaining < 0:
                    raise ValueError("Source text exceeds the import limit")
                pages.append(LocalPageEvidence(number, text))
                if not text and not has_visual_content:
                    has_visual_content = bool(
                        page.get_image_info() or page.get_drawings()
                    )
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise ValueError("Each source must be a readable PDF") from error
    if not has_visual_content and not any(page.text for page in pages):
        raise ValueError("A source has no extractable text or visual content")
    return tuple(pages)


def build_custom_evidence(
    sources: Sequence[LocalSource],
) -> tuple[LocalDocumentEvidence, ...]:
    """Validate three or more private examples and keep exact page ordinals.

    Empty pages in otherwise readable files remain visible for review.
    This does not infer a format, confirm rights, or qualify any output.
    """
    if len(sources) > MAX_SOURCES:
        raise ValueError("Too many assessment sources")
    for source in sources:
        if source.role not in _ROLES:
            raise ValueError("Unknown assessment source role")
        if len(source.content) > MAX_SOURCE_BYTES:
            raise ValueError("A source exceeds the file size limit")
    if sum(len(source.content) for source in sources) > MAX_TOTAL_BYTES:
        raise ValueError("Sources exceed the combined file size limit")
    if sum(source.role == "question-paper" for source in sources) < 3:
        raise ValueError("Provide at least three distinct question papers")

    seen_bytes: set[str] = set()
    seen_text: set[str] = set()
    evidence = []
    remaining = MAX_TOTAL_CHARACTERS
    for source in sources:
        digest = sha256(source.content).hexdigest()
        if digest in seen_bytes:
            raise ValueError("Duplicate assessment source")
        pages = _extract_pages(source.content, remaining)
        remaining -= sum(len(page.text) for page in pages)
        if source.role == "question-paper" and any(page.text for page in pages):
            normalized = unicodedata.normalize(
                "NFKC", " ".join(page.text for page in pages)
            ).casefold()
            text_digest = sha256(
                " ".join(normalized.split()).encode("utf-8")
            ).hexdigest()
            if text_digest in seen_text:
                raise ValueError("Duplicate question-paper text")
            seen_text.add(text_digest)
        seen_bytes.add(digest)
        evidence.append(LocalDocumentEvidence(source.role, digest, pages))
    return tuple(evidence)
