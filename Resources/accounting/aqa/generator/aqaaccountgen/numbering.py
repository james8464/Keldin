# Assign printed question numbers for AQA Accounting paper sections.

from __future__ import annotations


def question_number(paper_id: str, section_id: str, index: int) -> str:
    """Return the printed number for one question in a paper section."""
    if section_id == "A":
        if index < 10:
            return f"{index + 1:02d}"
        if paper_id == "paper_1":
            return ["11", "12", "13.1", "13.2"][index - 10]
        return ["11", "12.1", "12.2", "13"][index - 10]
    if section_id == "B":
        if paper_id == "paper_1":
            return ["14.1", "14.2", "15.1", "15.2", "15.3"][index]
        return [
            "14.1",
            "14.2",
            "14.3",
            "14.4",
            "15.1",
            "15.2",
            "15.3",
            "15.4",
        ][index]
    return str(16 + index)
