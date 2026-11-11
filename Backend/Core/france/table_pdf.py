"""Compare current generic material tables with their visible ruled cells."""

import math
from bisect import bisect_right
from dataclasses import dataclass
from itertools import pairwise

import pymupdf

from Backend.Core.france.code_layout import LEFT_MARGIN, RIGHT_MARGIN
from Backend.Core.france.whole_case_pdf import _compact

TOLERANCE = 0.5


@dataclass
class Grid:
    page: int
    bounds: pymupdf.Rect
    header: pymupdf.Rect
    xs: list[float]
    ys: list[float]
    cells: list[list[str]]


def _near(a, b):
    return abs(a - b) <= TOLERANCE


def _coordinates(values):
    result = []
    for value in sorted(values):
        if not result or not _near(value, result[-1]):
            result.append(value)
    return result


def _merge_vertical(lines):
    """ReportLab splits column rules at a repeated header; join only touching ink."""
    result = []
    for x in _coordinates(item[0] for item in lines):
        spans = sorted((start, end) for at, start, end in lines if _near(at, x))
        for start, end in spans:
            if (
                result
                and _near(result[-1][0], x)
                and start <= result[-1][2] + TOLERANCE
            ):
                result[-1] = (x, result[-1][1], max(end, result[-1][2]))
            else:
                result.append((x, start, end))
    return result


def _glyphs(page):
    result = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    if not char["c"].isspace():
                        result.append((char["c"], pymupdf.Rect(char["bbox"])))
    if len(result) > 100_000:
        raise ValueError("Trop de glyphes pour contrôler les cellules du tableau")
    return result


def _grids(page, number, top=0, bottom_limit=float("inf")):
    drawings = page.get_drawings()
    if len(drawings) > 10_000:
        raise ValueError("Trop de tracés pour contrôler les cellules du tableau")
    horizontal, vertical, headers = [], [], []
    width = page.rect.width - LEFT_MARGIN - RIGHT_MARGIN
    for drawing in drawings:
        if "s" in drawing["type"] and drawing.get("stroke_opacity", 0) >= 0.8:
            for item in drawing["items"]:
                if item[0] != "l":
                    continue
                first, second = item[1:]
                if not all(math.isfinite(v) for v in (*first, *second)):
                    raise ValueError("Coordonnées de tableau non finies")
                if _near(first.y, second.y):
                    horizontal.append(
                        (min(first.x, second.x), max(first.x, second.x), first.y)
                    )
                elif _near(first.x, second.x):
                    vertical.append(
                        (first.x, min(first.y, second.y), max(first.y, second.y))
                    )
        fill = drawing.get("fill")
        for item in drawing["items"]:
            if (
                item[0] == "re"
                and fill
                and len(fill) == 3
                and all(abs(channel - 232 / 255) < 0.01 for channel in fill)
                and drawing.get("fill_opacity", 0) >= 0.8
            ):
                rect = pymupdf.Rect(item[1])
                if (
                    _near(rect.x0, LEFT_MARGIN)
                    and _near(rect.width, width)
                    and rect.y0 >= top
                    and rect.y1 <= bottom_limit
                ):
                    headers.append(rect)
    vertical = _merge_vertical(vertical)
    glyphs = _glyphs(page)
    result = []
    for header in headers:
        bottoms = _coordinates(
            y1 for x, y0, y1 in vertical if _near(y0, header.y0) and y1 >= header.y1
        )
        if len(bottoms) != 1:
            raise ValueError("Limites verticales du tableau absentes ou ambiguës")
        bottom = bottoms[0]
        xs = _coordinates(
            x for x, y0, y1 in vertical if _near(y0, header.y0) and _near(y1, bottom)
        )
        ys = _coordinates(
            y
            for x0, x1, y in horizontal
            if _near(x0, header.x0)
            and _near(x1, header.x1)
            and header.y0 - TOLERANCE <= y <= bottom + TOLERANCE
        )
        if (
            not 3 <= len(xs) <= 9
            or not 3 <= len(ys) <= 32
            or not _near(xs[0], header.x0)
            or not _near(xs[-1], header.x1)
            or not _near(ys[0], header.y0)
            or not _near(ys[1], header.y1)
            or not _near(ys[-1], bottom)
            or any(b - a <= 2 * TOLERANCE for a, b in pairwise(xs))
            or any(b - a <= 2 * TOLERANCE for a, b in pairwise(ys))
        ):
            raise ValueError("Grille de tableau manquante ou colonnes effondrées")
        bounds = pymupdf.Rect(xs[0], ys[0], xs[-1], ys[-1])
        for x, y0, y1 in vertical:
            if (
                bounds.x0 - TOLERANCE <= x <= bounds.x1 + TOLERANCE
                and y0 >= bounds.y0 - TOLERANCE
                and y1 <= bounds.y1 + TOLERANCE
                and not (_near(y0, bounds.y0) and _near(y1, bounds.y1))
            ):
                raise ValueError("Séparation partielle de colonne dans le tableau")
        for x0, x1, y in horizontal:
            if (
                bounds.y0 - TOLERANCE <= y <= bounds.y1 + TOLERANCE
                and x0 >= bounds.x0 - TOLERANCE
                and x1 <= bounds.x1 + TOLERANCE
                and not (_near(x0, bounds.x0) and _near(x1, bounds.x1))
            ):
                raise ValueError("Séparation partielle de ligne dans le tableau")
        cells = [[[] for _ in xs[1:]] for _ in ys[1:]]
        for text, box in glyphs:
            centre = (box.tl + box.br) / 2
            if not bounds.contains(centre):
                continue
            if any(_near(centre.x, x) for x in xs) or any(
                _near(centre.y, y) for y in ys
            ):
                raise ValueError("Glyphe sur une limite ambiguë de cellule")
            row = bisect_right(ys, centre.y) - 1
            col = bisect_right(xs, centre.x) - 1
            cell = pymupdf.Rect(xs[col], ys[row], xs[col + 1], ys[row + 1])
            expanded = pymupdf.Rect(
                cell.x0 - TOLERANCE,
                cell.y0 - TOLERANCE,
                cell.x1 + TOLERANCE,
                cell.y1 + TOLERANCE,
            )
            if not expanded.contains(box):
                raise ValueError("Glyphe coupé ou déplacé entre cellules du tableau")
            cells[row][col].append(text)
        result.append(
            Grid(
                number,
                bounds,
                header,
                xs,
                ys,
                [[_compact("".join(value)) for value in row] for row in cells],
            )
        )
    return sorted(result, key=lambda grid: grid.bounds.y0)


def page_lines(page, omitted_headers=()):
    """Remove only complete text lines within validated continuation headers."""
    result = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            box = pymupdf.Rect(line["bbox"])
            if any(header.contains(box) for header in omitted_headers):
                continue
            result.append("".join(span["text"] for span in line["spans"]))
    return result


def check_material_tables(pages, exercises, starts, material_tables):
    """Bind ordered material grids before question one; return header omissions."""
    omissions, provenance = {}, []
    for index, exercise in enumerate(exercises):
        sources = material_tables[index]
        if not sources:
            continue
        first, heading_bottom = starts[index]
        last = starts[index + 1][0] if index + 1 < len(starts) else len(pages)
        # The unchanged renderer places the question bullet six points after its
        # frame padding, outside material cells. Use the source question ID.
        markers = [
            (page, word[1])
            for page in range(first, last)
            for word in pages[page].get_text("words")
            if word[4] == f"{exercise.questions[0].id}."
            and _near(word[0], LEFT_MARGIN + 12)
            and word[6:] == (0, 0)
        ]
        if len(markers) != 1:
            raise ValueError("Début des questions ambigu pour les tableaux")
        question_start = markers[0]
        available = [
            grid
            for number in range(first, question_start[0] + 1)
            for grid in _grids(
                pages[number],
                number,
                heading_bottom if number == first else 0,
                question_start[1] if number == question_start[0] else float("inf"),
            )
        ]
        available = [
            grid for grid in available if (grid.page, grid.bounds.y1) < question_start
        ]
        cursor = 0
        for label, material in sources:
            expected_header = [_compact(value) for value in material.columns]
            expected_rows = [
                [_compact(value) for value in row] for row in material.rows
            ]
            consumed, previous = 0, None
            while consumed < len(expected_rows):
                if cursor == len(available):
                    raise ValueError("Grille du tableau matériel absente")
                grid = available[cursor]
                cursor += 1
                if (
                    len(grid.xs) - 1 != len(expected_header)
                    or grid.cells[0] != expected_header
                ):
                    raise ValueError(
                        "Colonnes ou en-tête du tableau différents de la source"
                    )
                if previous is None:
                    before = [
                        line
                        for block in pages[grid.page].get_text("dict")["blocks"]
                        for line in block.get("lines", [])
                        if line["bbox"][3] <= grid.bounds.y0
                    ]
                    text = _compact(
                        "\n".join(
                            "".join(span["text"] for span in line["spans"])
                            for line in before
                        )
                    )
                    if _compact(label) not in text:
                        raise ValueError("Titre du tableau matériel absent")
                else:
                    if grid.page != previous.page + 1 or any(
                        not _near(a, b)
                        for a, b in zip(grid.xs, previous.xs, strict=True)
                    ):
                        raise ValueError("Continuation du tableau ambiguë")
                    omissions.setdefault(grid.page, []).append(grid.header)
                rows = grid.cells[1:]
                if not rows or rows != expected_rows[consumed : consumed + len(rows)]:
                    raise ValueError(
                        "Cellules ou lignes du tableau différentes de la source"
                    )
                consumed += len(rows)
                provenance.append(
                    {
                        "exercise": exercise.id,
                        "material": material.id,
                        "page": grid.page + 1,
                        "rows": len(rows),
                        "columns": len(expected_header),
                        "repeated_header": previous is not None,
                    }
                )
                previous = grid
        if cursor != len(available):
            raise ValueError("Grille supplémentaire dans les documents matériels")
    return omissions, provenance
