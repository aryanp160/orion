# Stage 1: Backend
FROM python:3.12-slim AS backend
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 2: Frontend build & serve
FROM node:22-alpine AS frontend
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm install
COPY apps/web/ .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
