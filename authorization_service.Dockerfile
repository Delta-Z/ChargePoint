# syntax=docker/dockerfile:1

FROM python:3

WORKDIR /

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY authorization_service /authorization_service/

ENV FLASK_APP=authorization_service.app
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_PORT=5000

ENTRYPOINT [ "flask", "run"]
EXPOSE 5000
