"""
app/server.py — FastAPI dashboard server for Airport Ground Ops.

Usage:
    python -m uvicorn app.server:app --reload --port 8000
    # or:
    python run_dashboard.py
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.simulator import run_comparison, get_graph, DEFAULT_MODEL, REPO_ROOT

app = FastAPI(title="Airport Ground Ops", version="1.0")

STATIC_DIR = Path(__file__).parent / "static"
MODELS_DIR = Path(REPO_ROOT) / "models"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/graph")
async def graph():
    return JSONResponse(get_graph())


@app.get("/api/models")
async def models():
    if not MODELS_DIR.exists():
        return JSONResponse([])
    zips = sorted(MODELS_DIR.glob("*.zip"))
    result = []
    for z in zips:
        result.append({"name": z.stem, "path": str(z)})
    return JSONResponse(result)


class SimRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=9999)
    model_name: str = Field(default="v5_anticipation_final")


@app.post("/api/simulate")
async def simulate(req: SimRequest):
    model_path = str(MODELS_DIR / f"{req.model_name}.zip")
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Model not found: {req.model_name}.zip")
    result = await run_in_threadpool(run_comparison, req.seed, model_path)
    return JSONResponse(result)
