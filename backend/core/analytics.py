"""Analítica numérica pura — sin LLM.

Funciones reutilizables por main.py y por el cliente Gemini cuando
necesite respaldar una interpretación con números reales.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


# ─── Forecast lineal ──────────────────────────────────────────────────────

def linear_forecast(valores: list[float], periodos: int = 6) -> dict[str, Any]:
    """Regresión lineal simple sobre una serie. Devuelve predicción + métricas."""
    if not valores or len(valores) < 2:
        raise ValueError("se requieren al menos 2 valores para proyectar")
    if periodos < 1:
        raise ValueError("periodos debe ser >= 1")

    y = np.asarray(valores, dtype=float)
    x = np.arange(len(y)).reshape(-1, 1)

    modelo = LinearRegression().fit(x, y)
    pendiente = float(modelo.coef_[0])
    intercepto = float(modelo.intercept_)
    r2 = float(modelo.score(x, y))

    x_futuro = np.arange(len(y), len(y) + periodos).reshape(-1, 1)
    proyeccion = modelo.predict(x_futuro).tolist()

    return {
        "historico": y.tolist(),
        "proyeccion": [round(v, 2) for v in proyeccion],
        "pendiente": round(pendiente, 4),
        "intercepto": round(intercepto, 4),
        "r2": round(r2, 4),
        "tendencia": "creciente" if pendiente > 0 else ("decreciente" if pendiente < 0 else "estable"),
    }


# ─── Anomalías ────────────────────────────────────────────────────────────

def detect_anomalies(valores: list[float], umbral_sigma: float = 2.0) -> dict[str, Any]:
    """Marca valores fuera de ±umbral_sigma desviaciones de la media."""
    if not valores:
        return {"anomalias": [], "media": 0, "desviacion": 0}

    arr = np.asarray(valores, dtype=float)
    media = float(arr.mean())
    desv = float(arr.std())
    if desv == 0:
        return {
            "anomalias": [],
            "media": round(media, 2),
            "desviacion": 0.0,
            "limite_superior": round(media, 2),
            "limite_inferior": round(media, 2),
        }

    limite_sup = media + umbral_sigma * desv
    limite_inf = media - umbral_sigma * desv

    anomalias = [
        {"indice": i, "valor": float(v), "tipo": "alto" if v > limite_sup else "bajo"}
        for i, v in enumerate(arr)
        if v > limite_sup or v < limite_inf
    ]

    return {
        "anomalias": anomalias,
        "media": round(media, 2),
        "desviacion": round(desv, 2),
        "limite_superior": round(limite_sup, 2),
        "limite_inferior": round(limite_inf, 2),
    }


# ─── Comparaciones ────────────────────────────────────────────────────────

def compare_groups(
    datos: list[dict],
    campo_grupo: str,
    campo_valor: str,
    agregacion: str = "sum",
) -> dict[str, Any]:
    """Agrupa registros por un campo y calcula sum/mean/count del valor.

    Devuelve el ranking ordenado (descendente) más diferencia top vs bottom.
    """
    if not datos:
        return {"ranking": [], "total": 0}

    df = pd.DataFrame(datos)
    if campo_grupo not in df.columns:
        raise ValueError(f"campo_grupo '{campo_grupo}' no existe en los datos")
    if campo_valor not in df.columns:
        raise ValueError(f"campo_valor '{campo_valor}' no existe en los datos")

    df[campo_valor] = pd.to_numeric(df[campo_valor], errors="coerce").fillna(0)

    agg_fn = {"sum": "sum", "mean": "mean", "count": "count", "max": "max", "min": "min"}.get(
        agregacion, "sum"
    )
    grouped = df.groupby(campo_grupo)[campo_valor].agg(agg_fn).sort_values(ascending=False)

    ranking = [
        {"grupo": str(idx), "valor": round(float(val), 2)}
        for idx, val in grouped.items()
    ]

    top = ranking[0] if ranking else None
    bottom = ranking[-1] if len(ranking) > 1 else None
    diferencia = None
    if top and bottom:
        diferencia = round(top["valor"] - bottom["valor"], 2)

    return {
        "ranking": ranking,
        "agregacion": agregacion,
        "top": top,
        "bottom": bottom,
        "diferencia_top_bottom": diferencia,
        "total": round(float(grouped.sum()), 2),
    }


# ─── Resumen estadístico rápido ───────────────────────────────────────────

def quick_stats(datos: Iterable[dict] | list[dict]) -> dict[str, Any]:
    """Estadísticas básicas por columna numérica."""
    df = pd.DataFrame(list(datos))
    if df.empty:
        return {"filas": 0, "columnas": []}

    numericas = df.select_dtypes(include=[np.number])
    resumen = {}
    for col in numericas.columns:
        resumen[col] = {
            "min": round(float(numericas[col].min()), 2),
            "max": round(float(numericas[col].max()), 2),
            "mean": round(float(numericas[col].mean()), 2),
            "sum": round(float(numericas[col].sum()), 2),
            "count": int(numericas[col].count()),
        }

    return {
        "filas": len(df),
        "columnas": df.columns.tolist(),
        "resumen_numerico": resumen,
    }
