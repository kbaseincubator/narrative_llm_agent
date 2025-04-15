# Use an official Python runtime as a parent image
FROM python:3.11-slim

RUN pip install poetry==1.8.3

# Set the working directory in the container
WORKDIR /app

ENV PATH="/root/.local/bin:$PATH" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Copy Poetry files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN apt-get update && apt-get install -y build-essential python3-dev
RUN pip install --upgrade pip
RUN pip install psutil==5.9.8
RUN poetry install && \
    rm -rf ${POETRY_CACHE_DIR}

# Copy the rest of the application code into the container
COPY . .

# Copy the MiniLM-L6-v2 model directory into the container
#COPY embedding_models/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/MiniLM-L6-v2 /app/embedding_models/MiniLM-L6-v2

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/app

# Change the working directory to where app.py is located
WORKDIR /app/narrative_llm_agent/user_interface

# Expose the port the app runs on
EXPOSE 8501

# Command to run the app
CMD ["poetry", "run", "streamlit", "run", "genome_annotation_pipeline_streamlit.py"]