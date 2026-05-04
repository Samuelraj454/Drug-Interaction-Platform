FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Since data pipeline runs background jobs and streaming, it will use producer/consumer scripts
# Default to a mock producer or hold open
CMD ["python", "openfda_producer.py"]
