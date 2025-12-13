# KBase Research Agent

An LLM-powered research agent that uses LangChain, LangGraph, and CrewAI to automatically build and execute bioinformatics workflows on the [DoE KBase](https://kbase.us/) infrastructure.

## Overview

The KBase Research Agent combines the power of Large Language Models with KBase's comprehensive suite of bioinformatics tools to automate research workflows. By leveraging advanced frameworks like LangChain, LangGraph, and CrewAI, the system can understand scientific goals, plan appropriate analyses, and execute complex workflows without manual intervention.

### Key Features

- **LLM-Driven Workflow Generation**: Uses LLMs to understand research objectives and generate appropriate analysis pipelines
- **KBase Integration**: Seamlessly accesses KBase's extensive bioinformatics tools and data
- **Multi-Agent Architecture**: Employs specialized agents for different tasks (metadata analysis, job execution, narrative writing)
- **Headless Operation**: Supports both interactive UI and automated batch processing
- **Real-time Monitoring**: Tracks job execution and provides progress updates

## Prerequisites

- Python 3.11 or 3.12
- [Poetry](https://python-poetry.org/) for dependency management
- Docker (optional, for containerized deployment)
- KBase authentication token
- API keys for LLM services (e.g., OpenAI, Anthropic, CBORG (for LBNL users - see https://cborg.lbl.gov))

## Installation & Development

### Using Poetry

Poetry is the recommended way to manage dependencies and run the project.

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install Dependencies**:
   ```bash
   poetry install
   ```

### Running Tests

Execute the test suite with coverage reporting:

```bash
poetry run pytest
```

This will:
- Run all tests in the `tests/` directory
- Generate an HTML coverage report in `htmlcov/index.html`
- Display coverage statistics in the terminal


## Docker

### Building the Docker Image

The project includes a Dockerfile for containerized deployment of the interactive application.

1. **Build the Image**:
   ```bash
   docker build -t kbase-research-agent:latest .
   ```

2. **Run the Container**:
   ```bash
   docker run -p 8050:8050 \
     -e KB_AUTH_TOKEN=your_kbase_token \
     -e CBORG_API_KEY=your_api_key \
     kbase-research-agent:latest
   ```

The Docker image:
- Uses Python 3.11 slim base image
- Installs all dependencies via Poetry
- Runs the interactive Dash-based UI on port 8050
- Includes a non-root user for security

## Configuration

Configuration is managed via `config.cfg`. Key settings include:

- **Service Endpoint**: URL of the KBase instance to connect to
- **LLM Settings**: API keys and model preferences for language models
- **Database Configuration**: Settings for vector databases and caching

Update `config.cfg` according to your deployment environment.

## Automated Pipeline Usage

The project includes scripts for automated batch processing of data through the analysis pipeline.

### Full Pipeline Script

The `scripts/full_pipeline.py` script performs end-to-end analysis:

1. Creates a KBase narrative
2. Builds and runs import cells for data ingestion
3. Waits for imports to complete
4. Executes the analysis pipeline with LLM-driven agents
5. Generates analysis reports

**Basic Usage**:
```bash
poetry run python scripts/full_pipeline.py \
  -k <KB_AUTH_TOKEN> \
  -p cborg \
  -l <CBORG_API_KEY> \
  -t <data_type> \
  <file_path>
```

**Supported Data Types**:
- `assembly`: Genomic assembly files
- `pe_reads_interleaved`: Paired-end interleaved reads
- `pe_reads_noninterleaved`: Paired-end non-interleaved reads
- `se_reads`: Single-end reads

**Example - Processing Assembled Genomes**:
```bash
poetry run python scripts/full_pipeline.py \
  -k $KB_AUTH_TOKEN \
  -p cborg \
  -l $CBORG_API_KEY \
  -t assembly \
  /path/to/genome.fasta
```

### Batch Pipeline Script

For processing multiple samples in parallel, use `scripts/run_batch_pipeline.py`:

```bash
poetry run python scripts/run_batch_pipeline.py
```

This script:
- Reads UPAs (Universal Permanent Addresses - these are KBase object ids) from `reads_upas.txt`
- Maintains a pool of 10 concurrent processes, which maximizes the use of a user's KBase queue access.
- Automatically submits jobs and monitors progress
- Logs results for each sample

**Setup**:
1. Create or update `reads_upas.txt` with one UPA per line
2. Set environment variables:
   ```bash
   export KB_AUTH_TOKEN=your_kbase_token
   export CBORG_API_KEY=your_cborg_api_key
   ```
3. Run the batch pipeline:
   ```bash
   poetry run python scripts/run_batch_pipeline.py
   ```

## Interactive Application

For interactive use, the project provides a Dash-based web UI:

```bash
poetry run python narrative_llm_agent/user_interface/ui_dash_hitl.py
```

The interface allows for:
- Manual workflow specification
- Real-time job monitoring
- Interactive refinement of workflow
- Report generation and visualization

## Project Structure

```
narrative_llm_agent/
├── agents/             # LLM agents for different tasks
├── kbase/              # KBase client utilities
│   ├── clients/        # Service clients (workspace, execution engine, etc.)
│   └── objects/        # KBase object representations
├── tools/              # Tool implementations for agent actions
├── workflow_graph/     # LangGraph workflow definitions
├── writer_graph/       # Report generation graphs
├── user_interface/     # Interactive UI components
└── util/               # Utility functions
tests/                  # Test suite
scripts/                # Standalone pipeline scripts
```

## Development Tips

### Using with Conda

Poetry can be used alongside Conda. After creating and activating a Conda environment:

```bash
conda activate your_env
poetry install
poetry run pytest
```

### Running Specific Tests

```bash
poetry run pytest tests/agents/test_coordinator_agent.py -v
```

### Code Quality

The project uses Ruff for linting. Check code quality:

```bash
poetry run ruff check .
```

## Authentication

### KBase Authentication

Set your KBase authentication token:

```bash
export KB_AUTH_TOKEN=your_token_here
```

Obtain a token from the [KBase user interface](https://kbase.us/).

### LLM Service Keys

Set API keys for your LLM provider:

```bash
export OPENAI_API_KEY=your_key_here
# or
export ANTHROPIC_API_KEY=your_key_here
# or
export CBORG_API_KEY=your_key_here
```

## Troubleshooting

- **Missing Dependencies**: Run `poetry install` to ensure all dependencies are installed
- **Configuration Issues**: Verify `config.cfg` has the correct service endpoint
- **Authentication Errors**: Confirm environment variables are set correctly
- **Test Failures**: Check that test data and mocks are properly configured

## Contributing

When contributing to this project:

1. Create a feature branch from `main`
2. Run tests locally: `poetry run pytest`
3. Ensure code quality: `poetry run ruff check .`
4. Submit a pull request with a clear description of changes

## License

See LICENSE file for details.
