# syntax=docker/dockerfile:1

# https://github.com/elastic/elasticsearch-py/issues/2716
FROM python:3.12-slim

WORKDIR /

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY authorization_worker /authorization_worker/

ENTRYPOINT ["celery", "-A", "authorization_worker.tasks", "worker", "--loglevel=INFO"]
