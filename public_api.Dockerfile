# syntax=docker/dockerfile:1

FROM python:3

WORKDIR /

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY authorization_worker /authorization_worker/
COPY public_api /public_api/

ENTRYPOINT [ "flask", "--app", "public_api.app", "run", "--port", "8080"]
EXPOSE 8080
