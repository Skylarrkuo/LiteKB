# syntax=docker/dockerfile:1.12
ARG NODE_IMAGE=node:24-alpine
ARG PYTHON_IMAGE=python:3.11-slim-bookworm
ARG LITEKB_MEDIA_NODES=0
ARG LITEKB_EXTENDED_PROVIDERS=0
ARG LITEKB_LOCAL_MODEL=0

FROM ${NODE_IMAGE} AS studio
ARG LITEKB_MEDIA_NODES
WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY ui/ ./
ENV VITE_LITEKB_MEDIA_NODES=$LITEKB_MEDIA_NODES NODE_OPTIONS=--max-old-space-size=4096
RUN npm run build && test -s dist/admin/index.html

FROM ${PYTHON_IMAGE} AS python-build
ARG LITEKB_MEDIA_NODES
ARG LITEKB_EXTENDED_PROVIDERS
ARG LITEKB_LOCAL_MODEL
ARG UV_VERSION=0.13.7
ENV TIKTOKEN_CACHE_DIR=/opt/litekb-tokenizers UV_LINK_MODE=copy
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gettext libffi-dev && \
    rm -rf /var/lib/apt/lists/*
COPY pyproject.toml installer/build-dependencies.sh ./
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --disable-pip-version-check --no-cache-dir "uv==${UV_VERSION}" && \
    sh build-dependencies.sh
COPY installer/sandbox.c ./
RUN mkdir -p sandbox/lib && gcc -O2 -shared -fPIC -o sandbox/lib/sandbox.so sandbox.c -ldl
COPY apps/ ./apps/
RUN find apps/locales -name '*.po' -exec sh -c 'for f do msgfmt -o "${f%.po}.mo" "$f"; done' sh {} +

FROM ${PYTHON_IMAGE} AS runtime
ARG LITEKB_MEDIA_NODES
ARG LITEKB_EXTENDED_PROVIDERS
ARG LITEKB_LOCAL_MODEL
ARG DOCKER_IMAGE_TAG=dev
WORKDIR /opt/maxkb-app
ENV PATH=/opt/py3/bin:$PATH \
    PYTHONUNBUFFERED=1 PYTHONPATH=/opt/maxkb-app/apps DJANGO_SETTINGS_MODULE=maxkb.settings \
    TIKTOKEN_CACHE_DIR=/opt/litekb-tokenizers MAXKB_VERSION=$DOCKER_IMAGE_TAG \
    LITEKB_MEDIA_NODES=$LITEKB_MEDIA_NODES LITEKB_EXTENDED_PROVIDERS=$LITEKB_EXTENDED_PROVIDERS \
    LITEKB_LOCAL_MODEL=$LITEKB_LOCAL_MODEL MAXKB_CONFIG_TYPE=ENV MAXKB_SANDBOX=1 \
    MAXKB_SANDBOX_HOME=/opt/maxkb-app/sandbox \
    MAXKB_SANDBOX_PYTHON_PACKAGE_PATHS=/opt/maxkb-app/sandbox/python-packages,/opt/maxkb/python-packages \
    MAXKB_SANDBOX_PYTHON_BANNED_HOSTS=127.0.0.0/8,localhost,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,postgres,redis,api,worker,local-model,0.0.0.0/32,::/0
RUN apt-get update && apt-get install -y --no-install-recommends gosu libpq5 && \
    if [ "$LITEKB_MEDIA_NODES" = 1 ]; then apt-get install -y --no-install-recommends ffmpeg; fi && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --no-create-home --home /opt/maxkb-app/sandbox --shell /usr/sbin/nologin --gid root sandbox && \
    mkdir -p -m 700 tmp data /opt/maxkb/logs && \
    find /etc -type f ! -path /etc/resolv.conf ! -path /etc/hosts ! -path /etc/hostname -exec chmod g-rx {} + && \
    chmod g-rwx /usr/local/bin/* /usr/bin/* /usr/sbin/* && chmod g+rx /usr/local/bin/python* && \
    ([ ! -e /usr/bin/ld.so ] || chmod g+rx /usr/bin/ld.so) && \
    chmod -R g-rwx /var/lock && chmod g-rwx /var/tmp /tmp && chmod g+rx /tmp
COPY --from=python-build /opt/py3 /opt/py3
COPY --from=python-build /opt/litekb-tokenizers /opt/litekb-tokenizers
COPY --from=python-build --chmod=550 /build/sandbox ./sandbox
COPY --from=python-build --chmod=700 /build/apps ./apps
COPY --from=studio --chmod=700 /build/ui/dist ./ui/dist
COPY --chmod=700 main.py ./
COPY --chmod=644 LICENSE ./
COPY --chmod=500 installer/litekb-entrypoint.sh /usr/local/bin/litekb
RUN --network=none --mount=type=tmpfs,target=/opt/maxkb/logs --mount=type=tmpfs,target=/opt/maxkb-app/data \
    --mount=type=tmpfs,target=/tmp \
    PYTHONDONTWRITEBYTECODE=1 MAXKB_ENABLE_FORCE_GC=0 python -c \
    'from maxkb.wsgi.web import application; from django.urls import resolve; assert callable(application) and resolve("/health/ready").url_name == "ready"'
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=6s --start-period=60s --retries=3 CMD ["/usr/local/bin/litekb", "health"]
ENTRYPOINT ["/usr/local/bin/litekb"]
CMD ["api"]
