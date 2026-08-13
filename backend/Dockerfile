FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

COPY . /app

EXPOSE 8000
