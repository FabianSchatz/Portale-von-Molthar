# Build the React frontend.
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Run the API, which also serves frontend/dist at "/".
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
# Editable install keeps the code in /app so the API finds /app/frontend/dist.
RUN pip install --no-cache-dir -e ".[server]"
COPY --from=frontend /app/frontend/dist frontend/dist
ENV PORT=8000
CMD ["sh", "-c", "uvicorn portale_von_molthar.entrypoints.api:app --host 0.0.0.0 --port $PORT"]
