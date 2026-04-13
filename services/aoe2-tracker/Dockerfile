FROM python:3.11-slim

WORKDIR /code

# Install shared group-lore package
COPY packages/group-lore/ /tmp/group-lore/
RUN pip install --no-cache-dir /tmp/group-lore/

# Copy and install dependencies
COPY services/aoe2-tracker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY services/aoe2-tracker/app/ ./app/

# Run the bot
CMD ["python", "-m", "app.main"]
