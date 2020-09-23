FROM python:3.8-alpine

COPY dist/*.whl /tmp
RUN pip install /tmp/*.whl

VOLUME "/build"
WORKDIR /build

ENTRYPOINT "/usr/local/bin/docker-prefab"
