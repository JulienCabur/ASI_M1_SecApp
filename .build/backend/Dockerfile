FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt update && apt install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt remove --purge -y perl # Remove Perl to mitigate vulnerabilities

COPY src/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/backend/ ./

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
