FROM alpine:edge

COPY *.whl /tmp
COPY repositories /etc/apk/repositories
COPY entrypoint /entrypoint

RUN apk -U add python3 py3-pip tzdata podman buildah curl jq && \
    pip3 install /tmp/*.whl && \
    /bin/rm -fr /root/.cache /var/cache && \
    find / -type d -name __pycache__ -exec /bin/rm -fr {} + && \
    find / -depth -type f -name '*.pyc' -exec /bin/rm -fr {} + && \
    find / -depth -type f -name '*.whl' -exec /bin/rm -fr {} +

VOLUME "/build"
WORKDIR /build

ENTRYPOINT ["/entrypoint"]
