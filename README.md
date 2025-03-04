# narrative_llm_agent
A set of tools to use LLMs to help build and execute a KBase Narrative workflow.

This uses [Poetry](https://python-poetry.org/) to handle requirements.

So, install that first.

## Installation
For development, using Poetry is the easiest way to go.
1. `poetry shell` makes a new local environment
2. `poetry install` installs all the dependencies
3. `poetry run pytest` runs tests and produces a coverage HTML in `htmlcov/index.html`

## Building
With everything else installed, just run `poetry build`.

## Configuration
`config.cfg` has the configuration for the package. Mostly, you'll need to set the service endpoint to wherever you're trying to run this.

## Bill's development workflow
Mostly I've been developing against this locally on my laptop. I'm sure there are ways to wire up some IDE to run remotely through an ssh tunnel, but I haven't bothered. I'll dev locally, run tests, push to a branch, then switch over to a console on a remote host, pull, and `poetry build`. Then the build products are on the remote PYTHONPATH already and usable.

## Mixing Poetry and Conda
That mostly just works using the above workflow. Poetry is (primarily) a package management tool, so it integrates with the build tools and such. Conda is an environment management tool. So once you have a conda environment set up, you can skip the `poetry shell` step above, and just run `poetry install` in your conda environment.

# TODO list
* migrate tools from agents to separate modules
* assign specific tools to tasks (after separation from agents)
* convert to langgraph agents
* convert to only using environment variables / singleton auth module / other more sensible solution for auth token control
* convert remaining tools to langchain tool ecosystem
* convert data objects to Pydantic:
  * kbase/clients/execution_engine.py
    * JobState
    * NarrativeCellInfo
    * JobInput
    * JsonRpcError
  * kbase/clients/workspace.py
    * WorkspaceObjectId
    * WorkspaceInfo
    * ObjectInfo
  * kbase/objects/narrative.py
    * Narrative
    * 
