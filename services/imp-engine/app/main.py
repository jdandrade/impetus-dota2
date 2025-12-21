"""
IMP Engine - Dota 2 Performance Scoring Microservice
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.scoring import calculate_imp_score
from app.models.request import CalculateIMPRequest
from app.models.response import CalculateIMPResponse

app = FastAPI(
    title="IMP Engine",
    description="Dota 2 Performance Scoring Microservice for Impetus",
    version="0.5.0",
)

# CORS configuration - supports both local development and production
# Set ALLOWED_ORIGINS env var for production (comma-separated URLs or * for all)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")

# Support wildcard for all origins
if allowed_origins_env.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if allowed_origins != ["*"] else False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - useful for Railway/Render health checks."""
    return {"service": "IMP Engine", "status": "running", "version": "0.5.0"}


@app.post("/api/v1/calculate-imp", response_model=CalculateIMPResponse)
async def calculate_imp(request: CalculateIMPRequest) -> CalculateIMPResponse:
    """
    Calculate the IMP (Impetus Performance) score for a player's match.

    Accepts raw match statistics and returns a normalized performance score
    with a breakdown of contributing factors.
    """
    return calculate_imp_score(request)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
