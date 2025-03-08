# syntax=docker/dockerfile:1

FROM python:3

WORKDIR /

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY authorization_worker /authorization_worker/

ENTRYPOINT ["celery", "-A", "authorization_worker.tasks", "worker", "--loglevel=INFO"]
