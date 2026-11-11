"""Shared physical code-line limits, without modifying printable source."""

from collections.abc import Iterator
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth

from Backend.Core.fonts import register_font
from Backend.Core.france.code_fences import fenced_parts

CODE_LAYOUT_POLICY = "fr-nsi-v36-code-layout-v1"
CODE_FENCE_PATTERN = r"```(?:python|sql)?[ \t]*(?:\r?\n)?"
LEFT_MARGIN = 70
RIGHT_MARGIN = 54
_UNPRINTABLE_SEPARATORS = frozenset("\x85\u2028\u2029")


class CodeLayoutError(ValueError):
    """An unchanged source line cannot fit the selected readable print mode."""


@dataclass(frozen=True)
class CodeLayout:
    font_name: str
    font_size: int
    content_width: float = A4[0] - LEFT_MARGIN - RIGHT_MARGIN - 12
    question_width: float = A4[0] - LEFT_MARGIN - RIGHT_MARGIN - 42

    @property
    def exercise_heading_size(self) -> int:
        return self.font_size + 2

    def columns(self, width: float) -> int:
        return int(width // stringWidth("M", self.font_name, self.font_size))


def code_layout(large_print: bool) -> CodeLayout:
    if type(large_print) is not bool:
        raise ValueError("Le mode de mise en page doit être booléen")
    return CodeLayout(
        register_font("AQACourier", fallback="Courier"), 16 if large_print else 12
    )


def code_blocks(text: str) -> Iterator[str]:
    for part in fenced_parts(text):
        if part.language is not None and part.text.strip():
            yield part.text.strip("\r\n")


def require_code_width(
    source: str,
    font_name: str,
    font_size: float,
    available_width: float,
    *,
    location: str = "code",
) -> None:
    # ReportLab's Preformatted splits on LF only. Other Unicode line
    # separators still occupy space on the line that will be painted.
    for number, line in enumerate(source.split("\n"), 1):
        width = stringWidth(line, font_name, font_size)
        if width > available_width:
            raise CodeLayoutError(
                f"Une ligne de code dépasse la largeur disponible ({location}, "
                f"ligne {number} : {width:.2f} pt > {available_width:.2f} pt). "
                "Rédiger un nouvel exercice avec des lignes plus courtes, sans "
                "modifier automatiquement le programme avant de publier le PDF."
            )
        separator = next(
            (char for char in line if char in _UNPRINTABLE_SEPARATORS), None
        )
        if separator is not None:
            raise CodeLayoutError(
                f"Le code contient un séparateur non imprimable "
                f"({location}, ligne {number}, U+{ord(separator):04X})."
            )
