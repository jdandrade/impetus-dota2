FROM python:3.11-slim

WORKDIR /code

# Install dependencies
# Path is relative to services/imp-engine (Railway root directory)
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy app code
COPY app /code/app

# Run the server (Port 8000 is standard, but use $PORT if env var exists)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
