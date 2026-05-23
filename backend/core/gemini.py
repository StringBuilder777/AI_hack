"""Cliente Gemini — análisis de datos JSON → métricas + interpretación + gráficas."""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import google.generativeai as genai


class Modelo(str, Enum):
    FAST = "gemini-2.5-flash-lite-preview-06-17"
    MAIN = "gemini-2.5-flash"


SYSTEM_PROMPT_ANALISIS = """Eres el cerebro analítico de AI_Hack.
Recibes datos JSON y una pregunta del usuario sobre operaciones técnicas (ROCEEL).
Responde ÚNICAMENTE con JSON válido — sin backticks, sin texto extra, sin markdown.

Esquema obligatorio:
{
  "metricas": [{"label": "string corto", "valor": "string con unidad"}],
  "interpretacion": "2-4 oraciones en español explicando hallazgos y recomendaciones",
  "graficas": [{
    "titulo": "string",
    "tipo": "bar|line|pie|doughnut|horizontal_bar|scatter",
    "datos": {
      "labels": ["string"],
      "datasets": [{"label": "string", "data": [number]}]
    }
  }]
}

Reglas:
- Genera 3-4 métricas KPI accionables.
- Genera 2-3 gráficas que ilustren los hallazgos.
- Tipo de gráfica: bar para rankings, line para series temporales, pie/doughnut para proporciones, scatter para correlaciones.
- Si los datos vienen con horas estimadas vs reales, calcula desviaciones (%).
- Si hay técnicos, clientes o actividades, identifica los más relevantes.
- Si la pregunta menciona predicción/proyección, devuelve datasets con la serie histórica + proyección.
- Si la pregunta menciona anomalías, marca outliers en la interpretación.
"""


@dataclass
class GeminiClient:
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    _models: dict[Modelo, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.api_key:
            print("[Gemini] ⚠ GEMINI_API_KEY no configurada")
            return
        genai.configure(api_key=self.api_key)
        for modelo in Modelo:
            try:
                self._models[modelo] = genai.GenerativeModel(modelo.value)
                print(f"[Gemini] modelo cargado: {modelo.name} → {modelo.value}")
            except Exception as e:
                print(f"[Gemini] error cargando {modelo.name}: {e}")

    def _get_model(self, modelo: Modelo) -> Any:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY no configurada")
        if modelo not in self._models:
            self._models[modelo] = genai.GenerativeModel(modelo.value)
        return self._models[modelo]

    @staticmethod
    def _strip_json(text: str) -> str:
        text = text.strip()
        m = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
        if m:
            return m.group(1)
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            return m.group(1)
        return text

    async def ask(self, prompt: str, modelo: Modelo = Modelo.MAIN, system: str | None = None) -> str:
        model = self._get_model(modelo)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        def _call() -> str:
            resp = model.generate_content(full_prompt)
            return resp.text or ""

        return await asyncio.to_thread(_call)

    async def analyze(
        self,
        pregunta: str,
        datos: list | dict,
        contexto_extra: str | None = None,
    ) -> dict:
        ctx = f"\nContexto adicional (resumen numérico calculado):\n{contexto_extra}\n" if contexto_extra else ""
        datos_json = json.dumps(datos, ensure_ascii=False, default=str)
        if len(datos_json) > 20000:
            datos_json = datos_json[:20000] + "...[truncado]"

        prompt = f"""{ctx}
Pregunta del usuario: {pregunta}

Datos:
{datos_json}

Devuelve ÚNICAMENTE el JSON con el esquema indicado."""

        raw = await self.ask(prompt, Modelo.MAIN, system=SYSTEM_PROMPT_ANALISIS)
        cleaned = self._strip_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"[Gemini.analyze] JSON inválido: {e}\nRaw: {raw[:500]}")
            return {
                "metricas": [{"label": "Error de parsing", "valor": "Respuesta inválida"}],
                "interpretacion": f"El modelo devolvió texto no parseable. Crudo: {raw[:300]}",
                "graficas": [],
            }


gemini = GeminiClient()
