"""Pediatric Oncology Clinic Digital Twin API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse

from app import __version__
from app.api.routes import router

app = FastAPI(
    title="Pediatric Oncology Clinic Digital Twin",
    version=__version__,
    description="Simulation of one pediatric oncology outpatient day.",
)
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/", include_in_schema=False)
def open_dashboard() -> RedirectResponse:
    return RedirectResponse("http://localhost:5173/")
