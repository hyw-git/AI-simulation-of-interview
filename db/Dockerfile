FROM postgres:15

RUN set -eux \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential git ca-certificates wget gnupg lsb-release \
       postgresql-server-dev-15 \
    && git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make && make install \
    && cd / \
    && rm -rf /tmp/pgvector \
    && apt-get remove -y git build-essential \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
