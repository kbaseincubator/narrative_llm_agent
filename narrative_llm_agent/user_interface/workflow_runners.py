import json
import os

from narrative_llm_agent.config import get_llm
from narrative_llm_agent.user_interface.constants import WORKFLOW_INSTANCES
from narrative_llm_agent.user_interface.kbase_loader import load_kbase_classes
from narrative_llm_agent.workflow_graph.graph_hitl import (
    ExecutionWorkflow,
)
from narrative_llm_agent.util.json_util import make_json_serializable
from narrative_llm_agent.agents.metadata_lang import MetadataAgent

def run_analysis_planning(narrative_id, reads_id, description, credentials):
    """Run the analysis planning phase only"""

    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            api_key = credentials.get("cborg_api_key")
            used_llm = "gpt-4.1-cborg"
        else:
            api_key = credentials.get("openai_api_key")
            used_llm = "gpt-4o-openai"

        # Set Neo4j environment variables if they exist
        # TODO: should probably be globally set at startup.
        neo4j_uri = credentials.get("neo4j_uri", os.environ.get("NEO4J_URI", ""))
        neo4j_username = credentials.get(
            "neo4j_username", os.environ.get("NEO4J_USERNAME", "")
        )
        neo4j_password = credentials.get(
            "neo4j_password", os.environ.get("NEO4J_PASSWORD", "")
        )

        if neo4j_uri:
            os.environ["NEO4J_URI"] = neo4j_uri
        if neo4j_username:
            os.environ["NEO4J_USERNAME"] = neo4j_username
        if neo4j_password:
            os.environ["NEO4J_PASSWORD"] = neo4j_password

        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            print(f"Error loading KBase classes: {result}")
            return {
                "narrative_id": narrative_id,
                "reads_id": reads_id,
                "description": description,
                "workflow_state": None,
                "error": result,
                "status": "error",
            }

        AnalysisWorkflow = result["AnalysisWorkflow"]

        # Create workflow instance
        workflow = AnalysisWorkflow(
            analyst_llm=used_llm,
            analyst_token=api_key,
            app_flow_llm=used_llm,
            app_flow_token=api_key,
            kbase_token=kb_auth_token,
        )

        # Run the planning phase only
        workflow_state = workflow.run(
            narrative_id=narrative_id, reads_id=reads_id, description=description
        )
        # Store workflow instance globally
        workflow_key = f"{narrative_id}_{reads_id}"
        WORKFLOW_INSTANCES[workflow_key] = workflow

        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": workflow_state,
            "workflow_key": workflow_key,
            "error": workflow_state.get("error"),
            "status": "awaiting_approval"
            if workflow_state.get("awaiting_approval")
            else "completed",
        }

    except Exception as e:
        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": None,
            "error": str(e),
            "status": "error",
        }



def generate_mra_draft(narrative_id: int, credentials: dict[str, str]):
    """Generate MRA draft using the MraWriterGraph"""
    kbase_token = credentials.get("kb_auth_token")
    provider = credentials.get("provider")
    if provider == "cborg":
        api_key = credentials.get("cborg_api_key")
        writer_llm = "gpt-o1-cborg"
    else:
        api_key = credentials.get("openai_api_key")
        writer_llm = "gpt-o1-openai"

    try:
        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {"mra_draft": None, "error": result}

        MraWriterGraph = result["MraWriterGraph"]
        Workspace = result["Workspace"]
        ExecutionEngine = result["ExecutionEngine"]

        # Create KBase clients
        ws_client = Workspace(token=kbase_token)
        ee_client = ExecutionEngine(token=kbase_token)

        # Create MRA writer
        mra_writer = MraWriterGraph(
            ws_client, ee_client, writer_llm, writer_token=api_key
        )

        # Run the MRA workflow
        mra_writer.run_workflow(narrative_id)

        return {
            "mra_draft": "The MRA draft has been successfully generated.",
            "error": None,
        }

    except Exception as e:
        return {"mra_draft": None, "error": str(e)}


def run_analysis_execution(workflow_state, credentials, workflow_key=None):
    """Run the analysis execution phase after approval"""
    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            used_llm = "gpt-4.1-cborg"
            api_key = credentials.get("cborg_api_key")
        else:
            used_llm = "gpt-4o-openai"
            api_key = credentials.get("openai_api_key")

        # Set Neo4j environment variables if they exist
        neo4j_uri = credentials.get("neo4j_uri", os.environ.get("NEO4J_URI", ""))
        neo4j_username = credentials.get("neo4j_username", os.environ.get("NEO4J_USERNAME", ""))
        neo4j_password = credentials.get("neo4j_password", os.environ.get("NEO4J_PASSWORD", ""))

        if neo4j_uri:
            os.environ["NEO4J_URI"] = neo4j_uri
        if neo4j_username:
            os.environ["NEO4J_USERNAME"] = neo4j_username
        if neo4j_password:
            os.environ["NEO4J_PASSWORD"] = neo4j_password

        # Create execution workflow instance
        execution_workflow = ExecutionWorkflow(
            analyst_llm=used_llm,
            analyst_token=api_key,
            validator_llm=used_llm,
            validator_token=api_key,
            app_flow_llm=used_llm,
            app_flow_token=api_key,
            writer_llm=used_llm,
            writer_token=api_key,
            kbase_token=kb_auth_token,
        )

        # Run the execution phase
        final_state = execution_workflow.run(workflow_state)

        # Make the final_state JSON serializable
        final_state_serializable = make_json_serializable(final_state)
        print("=== FINAL STATE ===")
        print(json.dumps(final_state, indent=2, default=str))

        # Clean up stored workflow instance if provided
        if workflow_key and workflow_key in WORKFLOW_INSTANCES:
            del WORKFLOW_INSTANCES[workflow_key]

        return {
            "final_state": final_state_serializable,
            "error": final_state_serializable.get("error"),
            "status": "completed" if final_state_serializable.get("results") else "error",
        }

    except Exception as e:
        print(f"an error occurred: {e}")
        return {"error": str(e), "status": "error"}


# Initialize metadata agent
def initialize_metadata_agent(credentials) -> MetadataAgent:
    """Initialize the metadata collection agent"""

    # Get credentials and set environment variables
    kb_auth_token = credentials.get("kb_auth_token", "")
    provider = credentials.get("provider", "openai")

    if provider == "cborg":
        api_key = credentials.get("cborg_api_key")
        used_llm = "gpt-4.1-cborg"
    else:
        api_key = credentials.get("openai_api_key")
        used_llm = "gpt-4o-openai"

    llm = get_llm(used_llm, api_key=api_key)
    return MetadataAgent(llm=llm, llm_name=used_llm, token=kb_auth_token)
    # metadata_agent = MetadataAgent(llm=llm, token=kb_auth_token)
    # return metadata_agent.agent_executor
