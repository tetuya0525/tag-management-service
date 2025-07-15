# ==============================================================================
# Dockerfile
# ==============================================================================
FROM python:3.12-slim
ENV PYTHONUNBUFFERED True
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "300", "main:app"]
