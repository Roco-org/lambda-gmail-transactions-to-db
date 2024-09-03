# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set the working directory
WORKDIR /usr/src/app

# Copy requirements file (if you have one) and install dependencies
# In this case, you don't need to add a requirements.txt if you're only using libraries installed below
# If you have a requirements.txt, uncomment the following two lines:
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Install the required Python packages directly
RUN pip install --no-cache-dir \
    imaplib2 \
    beautifulsoup4 \
    psycopg2-binary \
    pyyaml

# Copy the rest of the application code to the container
COPY . .

# Run the Python script
CMD ["python", "lambda_function.py"]
