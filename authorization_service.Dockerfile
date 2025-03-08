# syntax=docker/dockerfile:1

FROM python:3

WORKDIR /

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY authorization_service /authorization_service/

ENTRYPOINT [ "flask", "--app", "authorization_service.app", "run", "--port", "5000"]
EXPOSE 5000
