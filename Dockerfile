# One image for every use case. The Cloud Run job picks what to run through its args.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Run as a non-root user. runs/ is where every run writes result.json, tokens.jsonl
# and trace.jsonl; on Cloud Run a Cloud Storage bucket is mounted there.
RUN useradd --create-home harness && mkdir -p runs simulation/out && chown -R harness /app
USER harness

# Default: the whole simulated engagement in fake mode. No API key needed.
ENTRYPOINT ["python"]
CMD ["-m", "simulation.run_engagement"]
