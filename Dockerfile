FROM python:3.11.4-slim as base

RUN useradd -ms /bin/bash python
USER python

RUN mkdir /home/python/proxy
WORKDIR /home/python/proxy

COPY --chown=python:python . ./

WORKDIR /home/python/proxy

FROM base as production