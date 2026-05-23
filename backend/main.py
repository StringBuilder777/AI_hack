"""AI_Hack — FastAPI app principal.

Endpoints:
  GET  /api/health          → liveness
  POST /api/analyze         → pregunta + datos JSON → KPIs + interpretación + gráficas (Gemini)
  POST /api/forecast        → predicción lineal (sklearn)
  POST /api/compare         → comparación/ranking por grupo (pandas)
  POST /api/anomalies       → detección de outliers (numpy)
  POST /api/quick-stats     → resumen estadístico rápido (sin LLM)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.gemini import gemini
from core.analytics import (
    linear_forecast,
    detect_anomalies,
    compare_groups,
    quick_stats,
)

load_dotenv()

app = FastAPI(
    title="AI_Hack",
    description="Análisis de datos con IA — predicciones, comparaciones, anomalías y gráficas",
    version="0.1.0",
)

cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Modelos Pydantic ─────────────────────────────────────────────────────

class Metrica(BaseModel):
    label: str
    valor: str


class GraficaDataset(BaseModel):
    label: str
    data: list[float | None]


class GraficaDatos(BaseModel):
    labels: list[str]
    datasets: list[GraficaDataset]


class GraficaConfig(BaseModel):
    titulo: str
    tipo: str
    datos: GraficaDatos


class AnalyzeRequest(BaseModel):
    pregunta: str = Field(..., description="Pregunta en lenguaje natural")
    datos: list | dict = Field(..., description="Datos JSON crudos")
    incluir_stats: bool = Field(True, description="Si true, adjunta quick_stats al prompt")


class AnalyzeResponse(BaseModel):
    metricas: list[Metrica] = []
    interpretacion: str = ""
    graficas: list[GraficaConfig] = []


class ForecastRequest(BaseModel):
    valores: list[float]
    periodos: int = 6


class AnomaliasRequest(BaseModel):
    valores: list[float]
    umbral_sigma: float = 2.0


class CompareRequest(BaseModel):
    datos: list[dict]
    campo_grupo: str
    campo_valor: str
    agregacion: str = "sum"  # sum | mean | count | max | min


class QuickStatsRequest(BaseModel):
    datos: list[dict]


# ─── Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ai_hack",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Análisis principal con Gemini. Adjunta resumen numérico al prompt si incluir_stats=True."""
    try:
        contexto_extra: str | None = None
        if req.incluir_stats and isinstance(req.datos, list) and req.datos and isinstance(req.datos[0], dict):
            try:
                stats = quick_stats(req.datos)
                contexto_extra = (
                    f"Filas: {stats['filas']}, columnas: {stats['columnas']}. "
                    f"Resumen numérico: {stats.get('resumen_numerico', {})}"
                )
            except Exception as e:
                print(f"[analyze] quick_stats falló: {e}")

        result = await gemini.analyze(
            pregunta=req.pregunta,
            datos=req.datos,
            contexto_extra=contexto_extra,
        )

        return AnalyzeResponse(
            metricas=[Metrica(**m) for m in result.get("metricas", [])],
            interpretacion=result.get("interpretacion", ""),
            graficas=[GraficaConfig(**g) for g in result.get("graficas", [])],
        )
    except Exception as e:
        print(f"[/api/analyze] ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Error en análisis: {e}")


@app.post("/api/forecast")
async def forecast(req: ForecastRequest) -> dict[str, Any]:
    try:
        return linear_forecast(req.valores, req.periodos)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/anomalies")
async def anomalies(req: AnomaliasRequest) -> dict[str, Any]:
    try:
        return detect_anomalies(req.valores, req.umbral_sigma)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compare")
async def compare(req: CompareRequest) -> dict[str, Any]:
    try:
        return compare_groups(req.datos, req.campo_grupo, req.campo_valor, req.agregacion)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quick-stats")
async def stats(req: QuickStatsRequest) -> dict[str, Any]:
    try:
        return quick_stats(req.datos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Frontend estático (panel demo) ───────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))
