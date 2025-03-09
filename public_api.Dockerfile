# syntax=docker/dockerfile:1

FROM python:3

WORKDIR /

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY authorization_worker /authorization_worker/
COPY public_api /public_api/

ENV FLASK_APP=public_api.app
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8080

ENTRYPOINT [ "flask", "run" ]
EXPOSE 8080
