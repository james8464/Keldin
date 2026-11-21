"""The finding shared by family repair hooks and the whole-paper reviewer."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FindingKind = Literal[
    "answer_leakage",
    "self_answer_leakage",
    "duplicate_demand",
    "contradiction",
    "credit_mismatch",
]


class PaperFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: FindingKind
    target_id: str = Field(min_length=1, max_length=80)
    peer_id: str = Field(min_length=1, max_length=80)
    target_quote: str = Field(min_length=4, max_length=240)
    peer_quote: str = Field(min_length=4, max_length=240)
    reason: str = Field(min_length=4, max_length=320)
