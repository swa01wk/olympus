FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates bubblewrap \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY core core
COPY apps/scheduler_worker apps/scheduler_worker
COPY apps/execution_worker apps/execution_worker
COPY agents agents
COPY migrations migrations
COPY config config

RUN uv sync --frozen --no-dev
# Executors run pytest in target repos (existing tests, baselines, reproduction); keep in step with uv.lock.
RUN uv pip install --python /app/.venv/bin/python "pytest==9.1.1" "pytest-asyncio==1.4.0"

ENV PATH="/app/.venv/bin:$PATH"
# bubblewrap may require user namespaces; document seccomp unconfined for Docker.
ENV OLYMPUS_SANDBOX=bwrap

CMD ["python", "-m", "apps.execution_worker.main"]
