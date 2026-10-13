FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_ENV=production \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONPATH=/app/backend

WORKDIR /app

RUN addgroup --system edutrack && adduser --system --ingroup edutrack --home /home/edutrack edutrack

COPY backend/requirements/base.txt /app/backend/requirements/base.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/backend/requirements/base.txt

COPY backend/ /app/backend/
RUN chown -R edutrack:edutrack /app

USER edutrack
WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60 --access-logfile - --access-logformat '{\"timestamp\":\"%(t)s\",\"method\":\"%(m)s\",\"status\":%(s)s,\"response_time_seconds\":%(L)s}' --error-logfile -"]
