"""Pydantic models for underwriting inputs and outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class Beneficiary(BaseModel):
    relationship: str = Field(min_length=1)
    percentage: int = Field(ge=0, le=100)


class Applicant(BaseModel):
    age: int = Field(ge=18, le=75)
    gender: Literal["male", "female"]
    occupation: str | None = None
    smoking: bool
    bmi: float | None = Field(default=None, ge=10.0, le=60.0)


class HealthCondition(BaseModel):
    condition: str = Field(min_length=1)
    diagnosed_year: int | None = Field(default=None, ge=1900, le=2100)
    controlled: bool | None = None
    medication: str | None = None


class Coverage(BaseModel):
    product_code: str = Field(min_length=1)
    coverage_amount: int = Field(ge=10_000)
    coverage_period_years: int = Field(ge=1, le=30)
    premium_frequency: Literal["annual", "semi_annual", "quarterly", "monthly"]


class ApplicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(min_length=1)
    applicant: Applicant
    health_conditions: list[HealthCondition] = Field(default_factory=list)
    coverage: Coverage
    beneficiaries: list[Beneficiary] = Field(default_factory=list)


class UnderwritingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "APPROVED",
        "APPROVED_WITH_LOADING",
        "DECLINED",
        "REQUEST_MORE_INFO",
    ]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    tool_calls_made: list[str] = Field(default_factory=list)
    processing_time_ms: int = Field(ge=0)
