FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas
COPY prompts ./prompts
RUN pip install --no-cache-dir -e '.[test]'
RUN useradd -r -u 10001 app && mkdir -p /artifacts && chown app:app /artifacts
USER app
CMD ["uvicorn", "linguai_quality.api:app", "--host", "0.0.0.0", "--port", "8000"]
