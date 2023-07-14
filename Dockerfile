FROM python:3.10.8-alpine

RUN apk add git postgresql-dev
RUN mkdir /app
WORKDIR /app
ADD . /app
RUN git config --global http.sslVerify false

RUN pip install -e .