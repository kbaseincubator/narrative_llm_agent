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

# Create user and give ownership of database directories 
RUN mkdir -p /home/agent_runner && \
    useradd agent_runner -u96921 -d/home/agent_runner && \
    chown -R agent_runner:agent_runner /home/agent_runner && \
    chown -R agent_runner:agent_runner /app/narrative_llm_agent/agents/ && \
    chmod -R 775 /app/narrative_llm_agent/agents/

# Create and copy the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && \
    chown agent_runner:agent_runner /app/entrypoint.sh

# Change the working directory to where app.py is located
WORKDIR /app/narrative_llm_agent/user_interface

# Expose the port the app runs on
EXPOSE 8050

# Switch to the non-root user 
USER agent_runner

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Command to run the app
CMD ["poetry", "run", "python", "ui_dash_hitl.py"]
