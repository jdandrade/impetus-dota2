"""
Response models for the IMP Engine API.
Phase 14: Simplified for regression-based scoring.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ContributingFactor(BaseModel):
    """A single factor contributing to the IMP score."""

    name: str = Field(..., description="Name of the statistic")
    value: float = Field(..., description="Actual value of the stat")
    impact: Literal["positive", "neutral", "negative"] = Field(
        ..., description="Impact on score"
    )
    weight: float = Field(..., ge=0, le=50, description="Coefficient weight used")


class IMPData(BaseModel):
    """Core IMP score data."""

    imp_score: float = Field(..., ge=-65, le=65, description="Stratz-style IMP score (-65 to +65)")
    grade: Literal["S", "A", "B", "C", "D", "F"] = Field(..., description="Letter grade")
    percentile: int = Field(..., ge=0, le=100, description="Performance percentile")
    contributing_factors: list[ContributingFactor] = Field(
        ..., description="Breakdown of score contributors"
    )
    summary: str = Field(..., description="Human-readable performance summary")


class IMPMeta(BaseModel):
    """Metadata about the calculation."""

    engine_version: str = Field(..., description="IMP Engine version")
    calculated_at: str = Field(..., description="ISO timestamp of computation")


class CalculateIMPResponse(BaseModel):
    """Response payload for IMP score calculation."""

    success: bool = Field(..., description="Whether the calculation succeeded")
    data: IMPData = Field(..., description="IMP score data")
    meta: IMPMeta = Field(..., description="Calculation metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "data": {
                    "imp_score": 35.2,
                    "grade": "A",
                    "percentile": 78,
                    "contributing_factors": [
                        {
                            "name": "Tower Damage",
                            "value": 19459,
                            "impact": "positive",
                            "weight": 0.0015,
                        },
                        {
                            "name": "Deaths",
                            "value": 3,
                            "impact": "negative",
                            "weight": 3.36,
                        },
                    ],
                    "summary": "Excellent Carry performance",
                },
                "meta": {
                    "engine_version": "0.5.0-stratz-calibrated",
                    "calculated_at": "2024-01-15T14:32:00Z",
                },
            }
        }
    }
