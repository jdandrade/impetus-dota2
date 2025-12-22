FROM python:3.11-slim

WORKDIR /code

# Copy and install dependencies
COPY services/professor-impetus/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY services/professor-impetus/app/ ./app/

# Run the bot
CMD ["python", "-m", "app.main"]
