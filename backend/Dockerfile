FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-dejavu-core \
    libffi8 \
    libharfbuzz-subset0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    netcat-openbsd \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt /tmp/requirements/base.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir --index-url https://pypi.org/simple -r /tmp/requirements/base.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
