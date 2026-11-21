"""Candidate-visible chart labels and source booklet rows."""

from dataclasses import dataclass

from Backend.Core.exam_blueprints import GeneratedOption
from Backend.Core.subjects.selected_response import SelectedResponseContract


@dataclass(frozen=True)
class BreakEvenFigure:
    maximum_output: float
    maximum_value: float
    lines: tuple[tuple[str, float, float], ...]
    intersections: tuple[tuple[str, float, float], ...]

    @classmethod
    def from_contract(cls, contract: SelectedResponseContract) -> "BreakEvenFigure":
        values = {key: float(value) for key, value in contract.inputs.items()}
        before = values["fixed_cost_before"] / (
            values["price_before"] - values["variable_cost_before"]
        )
        after = values["fixed_cost_after"] / (
            values["price_after"] - values["variable_cost_after"]
        )
        maximum_output = max(before, after) * 1.35
        lines = (
            ("TR1", 0.0, values["price_before"]),
            ("TC1", values["fixed_cost_before"], values["variable_cost_before"]),
            ("TR2", 0.0, values["price_after"]),
            ("TC2", values["fixed_cost_after"], values["variable_cost_after"]),
        )
        return cls(
            maximum_output,
            max(start + rate * maximum_output for _, start, rate in lines),
            lines,
            (
                ("M", before, values["price_before"] * before),
                ("N", after, values["price_after"] * after),
            ),
        )

    def review_context(self) -> tuple[str, ...]:
        return (
            "Figure 1: change in the break-even point (unscaled axes). Positions "
            "below are relative to the visible graph, not printed monetary amounts.",
            "Horizontal: Output. Vertical: Costs / revenue.",
            *(
                f"{label}: left height {start / self.maximum_value:.3g}; "
                f"right height {(start + rate * self.maximum_output) / self.maximum_value:.3g}"
                for label, start, rate in self.lines
            ),
            *(
                f"{label}: horizontal {output / self.maximum_output:.3g}; "
                f"vertical {amount / self.maximum_value:.3g}"
                for label, output, amount in self.intersections
            ),
        )


def chart_values(option: GeneratedOption, extract: int = 0) -> list[float]:
    if not extract:
        return list(option.chart_values)
    multiplier = 1 + (extract - 1) * 0.03
    return [round(value * multiplier, 1) for value in option.chart_values]


def printed_points(
    option: GeneratedOption, values: list[float]
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (label, f"{value:.1f}")
        for label, value in zip(option.chart_labels, values, strict=True)
    )


def grouped_chart_title(title: str) -> str:
    return f"Market value and {title} sales (index values)"


def market_chart_values(option: GeneratedOption) -> list[float]:
    return [round(value * 5.4, 1) for value in option.chart_values]


def source_table_rows(option: GeneratedOption, index: int) -> list[list[str]]:
    values = chart_values(option, index)
    return [
        ["Measure", "2023", "2024", "2025"],
        ["Performance index", *(f"{value:.1f}" for value in values[2:5])],
        ["Employee engagement", f"{54 + index}%", f"{57 + index}%", f"{59 + index}%"],
        ["Capacity utilisation", f"{68 + index}%", f"{72 + index}%", f"{70 + index}%"],
    ]
