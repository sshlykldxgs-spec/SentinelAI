from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class Claim(Contract):
    text: str = Field(min_length=1, max_length=1200)
    kind: Literal['fact', 'computed', 'hypothesis', 'external_unverified']
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    metric_values: dict[str, float] = Field(default_factory=dict)


class Risk(Contract):
    supplier: str = Field(min_length=1, max_length=160)
    level: Literal['high', 'medium', 'low']
    reason: str = Field(min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


class Action(Contract):
    title: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=1200)
    owner: str = Field(min_length=1, max_length=100)
    deadline: str = Field(min_length=1, max_length=100)
    impact: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    requires_approval: bool = True


class StageOutput(Contract):
    summary: str = Field(min_length=1, max_length=4000)
    acceptance_conditions: list[str] = Field(default_factory=list, max_length=12)
    claims: list[Claim] = Field(default_factory=list, max_length=30)
    risks: list[Risk] = Field(default_factory=list, max_length=20)
    actions: list[Action] = Field(default_factory=list, max_length=12)
    review_decision: Literal['not_applicable', 'pass', 'needs_evidence', 'human_review'] = 'not_applicable'
    review_findings: list[str] = Field(default_factory=list, max_length=20)
    unresolved: list[str] = Field(default_factory=list, max_length=20)
