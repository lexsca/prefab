FROM python:3.8-alpine

COPY dist/*.whl /tmp
RUN pip install /tmp/*.whl && \
    /bin/rm -fr /root/.cache /var/cache && \
    find . -type d -name __pycache__ -exec /bin/rm -fr {} + && \
    find . -depth -type f -name '*.pyc' -exec /bin/rm -fr {} + && \
    find . -depth -type f -name '*.whl' -exec /bin/rm -fr {} +

VOLUME "/build"
WORKDIR /build

ENTRYPOINT "/usr/local/bin/docker-prefab"
