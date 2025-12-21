FROM python:3.11-slim

WORKDIR /code

# Install dependencies
# Paths are relative to repo root since Root Directory is /
COPY services/imp-engine/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy app code
COPY services/imp-engine/app /code/app

# Run the server (Port 8000 is standard, but use $PORT if env var exists)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
