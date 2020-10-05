ARG prefab_base
ARG prefab_wheels

FROM $prefab_wheels as wheels
FROM $prefab_base

COPY --from=wheels /wheels /wheels
COPY *.whl /wheels

RUN pip3 install /wheels/*.whl && \
    rm -fr /wheels && \
    find / -type d -name __pycache__ -exec /bin/rm -fr {} + && \
    find / -depth -type f -name '*.pyc' -exec /bin/rm -fr {} +

COPY entrypoint /entrypoint

ENTRYPOINT ["/entrypoint"]
