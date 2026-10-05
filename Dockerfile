FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 calculator \
    && mkdir /data && chown calculator:calculator /data
COPY --chown=calculator:calculator src ./src
USER calculator
ENV DATABASE_PATH=/data/calculator.db
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
