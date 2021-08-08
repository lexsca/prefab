ARG PREFAB_PACKAGES

FROM --platform=linux/amd64 $PREFAB_PACKAGES as packages
FROM --platform=linux/amd64 docker.io/library/python:3.8-alpine

COPY --from=packages /packages /packages
COPY app.py app.py

RUN apk -U add libxml2 libxslt && \
    pip install --upgrade pip && \
    pip3 install --no-index --find-links=/packages /packages/* && \
    rm -fr /var/cache/apk/* /packages

CMD ["python3", "app.py"]
