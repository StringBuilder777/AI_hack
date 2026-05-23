# AI_Hack

Backend Python + FastAPI dockerizado para análisis de datos con IA.
Recibe JSON, devuelve KPIs, interpretación y configuración de gráficas (Chart.js compatible).

Pensado para correr en **EC2** vía Docker y ser consumido por el frontend del proyecto **SoftwareInteligente / RH** (pestaña *Métricas → Análisis IA*).

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI |
| IA | Google Gemini (`gemini-2.5-flash`) |
| Análisis numérico | pandas + scikit-learn + numpy |
| Deploy | Docker + docker-compose |
| Frontend demo | HTML + Chart.js (panel standalone) |

---

## Estructura

```
AI_Hack/
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py             # FastAPI app
│   └── core/
│       ├── gemini.py       # cliente Gemini → analyze(pregunta, datos)
│       └── analytics.py    # forecast / anomalies / compare / quick_stats
└── frontend/
    └── index.html          # panel demo (Chart.js)
```

---

## Variables de entorno

Copia `.env.example` a `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | — | **Requerida.** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `PORT` | 8000 | Puerto interno del contenedor |
| `CORS_ORIGINS` | `*` | Orígenes permitidos (en prod: `https://tu-dominio.com`) |
| `LOG_LEVEL` | info | debug / info / warning / error |

---

## Levantar local

```bash
docker compose up --build
# panel demo:   http://localhost:8000/
# API health:   http://localhost:8000/api/health
```

Sin Docker:

```bash
cd backend
pip install -r requirements.txt
export GEMINI_API_KEY=AIza_tu_key
uvicorn main:app --reload --port 8000
```

---

## Endpoints

### `GET /api/health`

```json
{ "status": "ok", "service": "ai_hack", "gemini_configured": true }
```

### `POST /api/analyze` — análisis general con IA

Request:
```json
{
  "pregunta": "¿Qué técnico tiene mayor desviación de horas?",
  "datos": [
    {"tecnico":"Juan","horas_estimadas":4,"horas_reales":6},
    {"tecnico":"María","horas_estimadas":3,"horas_reales":2}
  ],
  "incluir_stats": true
}
```

Response:
```json
{
  "metricas": [{"label":"Top desviación","valor":"Juan (+50%)"}],
  "interpretacion": "Juan tiene la mayor desviación positiva...",
  "graficas": [
    {
      "titulo": "Desviación por técnico",
      "tipo": "bar",
      "datos": {
        "labels": ["Juan","María"],
        "datasets": [{"label":"% desviación","data":[50,-33]}]
      }
    }
  ]
}
```

### `POST /api/forecast` — predicción lineal (sin LLM)

```json
{ "valores": [10, 12, 15, 18, 22], "periodos": 3 }
```

### `POST /api/compare` — ranking por grupo

```json
{
  "datos": [...],
  "campo_grupo": "cliente",
  "campo_valor": "horas_reales",
  "agregacion": "sum"
}
```

### `POST /api/anomalies` — outliers ±N sigma

```json
{ "valores": [10,11,10,12,40,11], "umbral_sigma": 2.0 }
```

### `POST /api/quick-stats` — resumen estadístico rápido

```json
{ "datos": [{"a":1,"b":2}, {"a":3,"b":4}] }
```

---

## Deploy en EC2

1. Lanzar instancia (Amazon Linux 2023 t3.small o superior).
2. Instalar Docker:
   ```bash
   sudo dnf install -y docker
   sudo systemctl enable --now docker
   sudo usermod -aG docker ec2-user
   newgrp docker
   sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose
   ```
3. Clonar y arrancar:
   ```bash
   git clone <repo> AI_Hack && cd AI_Hack
   cp .env.example .env && nano .env   # poner GEMINI_API_KEY y CORS_ORIGINS
   docker compose up -d --build
   ```
4. Security Group: abrir puerto **8000** (o ponerlo detrás de nginx/ALB).

---

## Integración con SoftwareInteligente / RH

El frontend de RH (`apps/rh/src/components/metricas/IAPlaceholder.jsx`) llama a este backend
a través del proxy de Vite (mismo patrón que el backend RH).

En `apps/rh/vite.config.js` está configurado:

```js
'/ai_hack': {
  target: 'http://localhost:8000',     // ← cambia esto a http://<ec2-host>:8000 cuando despliegues
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/ai_hack/, ''),
}
```

El servicio `apps/rh/src/services/iaHack.service.js` usa `baseURL = '/ai_hack'`, así que
solo necesitas cambiar el `target` del proxy. No hay `.env` que tocar.
