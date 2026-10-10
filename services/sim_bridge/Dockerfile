# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS prod
COPY requirements.txt ./
COPY services/sim_bridge/requirements.txt ./services/sim_bridge/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r services/sim_bridge/requirements.txt
COPY src/ ./src/
COPY services/ ./services/
EXPOSE 8000
CMD ["uvicorn","services.sim_bridge.app:app","--host","0.0.0.0","--port","8000"]

FROM base AS dev
COPY requirements.txt ./
COPY services/sim_bridge/requirements.txt ./services/sim_bridge/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r services/sim_bridge/requirements.txt
COPY src/ ./src/
COPY services/ ./services/
EXPOSE 8000
CMD ["uvicorn","services.sim_bridge.app:app","--host","0.0.0.0","--port","8000","--reload"]
