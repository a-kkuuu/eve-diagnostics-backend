FROM python:3.12-slim

# Create a non-root user
RUN groupadd -r eveuser && useradd -r -g eveuser eveuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and alembic files
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Give ownership to the non-root user
RUN chown -R eveuser:eveuser /app

USER eveuser

# The entrypoint command will be overridden in docker-compose for migrations + startup,
# but we provide a default uvicorn startup.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
