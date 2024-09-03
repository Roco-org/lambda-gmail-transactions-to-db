FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

RUN pip install --no-cache-dir \
    imaplib2 \
    beautifulsoup4 \
    psycopg2-binary \
    pyyaml


COPY . .

CMD ["python", "lambda_function.py"]
