FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements-dev.lock ./
COPY app ./app
RUN pip install --no-cache-dir -r requirements-dev.lock && pip install --no-cache-dir --no-deps .
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home tracker
USER tracker
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
