"""
A script that runs a full annotation pipeline.
Start with having files uploaded to a staging area.
Given the full file path and data type (and other params needed for import)
1. Create narrative
2. Build import cell
3. Run import cell
4. Wait for finish
5. Get import data object
6. Run headless agentic annotation pipeline
"""
import logging

from typing import Any
from pydantic import BaseModel
import argparse
import json

from narrative_llm_agent.agents.metadata_lang import MetadataAgent
from narrative_llm_agent.config import get_llm
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
from narrative_llm_agent.kbase.clients.narrative_service import NarrativeService
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.tools.job_tools import run_job
from narrative_llm_agent.workflow_graph.graph_hitl import AnalysisWorkflow, ExecutionWorkflow
from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowState
from narrative_llm_agent.writer_graph.mra_graph import MraWriterGraph

class PipelineConfig(BaseModel):
    kbase_token: str
    llm_provider: str
    llm_token: str
    narrative_name: str
    input_file_path: str
    input_data_type: str
    input_data_params: dict

def parse_args() -> PipelineConfig:
    parser = argparse.ArgumentParser(description="Run full KBase LLM Annotation Agent pipeline")
    parser.add_argument(
        "-k", "--kbase_token", help="KBase Auth Token", required=True
    )
    parser.add_argument(
        "-p", "--llm_provider", help="LLM Provider (CBORG or OpenAI)", required=True
    )
    parser.add_argument(
        "-l", "--llm_token", help="LLM API key", required=True
    )
    parser.add_argument(
        "-f", "--input_file_path", help="staging area file path to data object", required=True
    )
    parser.add_argument(
        "-t", "--input_data_type", help="staging area file data type to import as", required=True
    )
    args = parser.parse_args()

    file_name = args.input_file_path.split('/')[-1]
    input_params = data_type_to_params(args.input_data_type, args.input_file_path, file_name)
    narrative_name = f"LLM Agent Annotation for {file_name}"
    config = PipelineConfig(
        kbase_token=args.kbase_token,
        llm_provider=args.llm_provider,
        llm_token=args.llm_token,
        narrative_name=narrative_name,
        input_file_path=args.input_file_path,
        input_data_type=args.input_data_type,
        input_data_params=input_params
    )
    return config

def data_type_to_params(data_type: str, file_path: str, file_name: str) -> dict[str, Any]:
    if data_type == "assembly":
        return {
            "app_id": "kb_uploadmethods/import_fasta_as_assembly_from_staging",
            "params": {
                "staging_file_subdir_path": file_path,
                "assembly_name": file_name + "_assembly",
                "type": "mag",
                "min_contig_length": 500
            }
        }
    else:
        raise ValueError(f"Unsupported data type '{data_type}'")

def import_data_file(narr_id: int, app_id: str, app_params: dict[str, Any], token: str) -> str:
    """
    Imports a data file from the staging service into a narrative and returns the
    generated new object UPA.
    # TODO: update to a bulk import cell later.
    """
    ee = ExecutionEngine(token=token)
    nms = NarrativeMethodStore()
    ws = Workspace(token=token)
    result = run_job(narr_id, app_id, app_params, ee, nms, ws)
    if result.job_error:
        logging.error(result.job_error)
        logging.error(result.model_dump_json(indent=4))
        raise RuntimeError(result.job_error)
    if len(result.created_objects) > 1:
        logging.error(result.model_dump_json(indent=4))
        raise RuntimeError(f"Unexpected import results: {result}")
    return result.created_objects[0].object_upa

def process_metadata(narr_id: int, obj_upa: str, config: PipelineConfig):
    ws = Workspace(token=config.kbase_token)
    obj_info = ws.get_object_info(obj_upa)
    meta_prompt = f"""I am working with narrative id {narr_id} and object UPA {obj_upa}.
This object has the registered metadata dictionary: {obj_info.metadata}. It is a MAG assembly.

My goal is to perform any relevant quality control on the assembly, then annotate it using a KBase
assembly tool that is useful for MAG data. quality assurance and control should be done at each step.
I want to end with a taxonomic analysis and prediction for the annotated genome.

The data was gathered from soil samples. I have no other information about the data source or techonology used
to generate it (i.e. sequencing machine, protocol, etc.)
"""
    if config.llm_provider == "cborg":
        used_llm = "gpt-4.1-cborg"
    else:
        used_llm = "gpt-4o-openai"

    llm = get_llm(used_llm, api_key=config.llm_token)
    meta_agent = MetadataAgent(llm=llm, llm_name=used_llm, token=config.kbase_token)
    response, token_count = meta_agent.invoke({
        "input": meta_prompt,
        "chat_history": []
    })
    logging.info(f"response: {response}")
    logging.info(f"token count: {token_count}")
    return response


def run_analysis_workflow(narr_id: int, obj_upa: str, meta_context: str, config: PipelineConfig) -> dict:
    # Create workflow instance

    # Get credentials and set environment variables
    if config.llm_provider == "cborg":
        used_llm = "gpt-4.1-cborg"
    else:
        used_llm = "gpt-4o-openai"

    workflow = AnalysisWorkflow(
        analyst_llm=used_llm,
        analyst_token=config.llm_token,
        app_flow_llm=used_llm,
        app_flow_token=config.llm_token,
        kbase_token=config.kbase_token,
    )

    description = f"""
The user has uploaded assembly data into the narrative.
I want you to generate an analysis plan for annotating the uploaded assembly into genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe.

NEVER suggest an app from the NarrativeViewers module. This includes any app with "NarrativeViewers" in its app_id.

Here is additional context: {meta_context}
"""

    # Run the planning phase only
    return workflow.run(
        narrative_id=narr_id, reads_id=obj_upa, description=description
    )


def run_execution_workflow(analysis_state: WorkflowState, config: PipelineConfig) -> WorkflowState:
    # Get credentials and set environment variables
    if config.llm_provider == "cborg":
        used_llm = "gpt-4.1-cborg"
    else:
        used_llm = "gpt-4o-openai"

    # Create execution workflow instance
    execution_workflow = ExecutionWorkflow(
        analyst_llm=used_llm,
        analyst_token=config.llm_token,
        validator_llm=used_llm,
        validator_token=config.llm_token,
        app_flow_llm=used_llm,
        app_flow_token=config.llm_token,
        writer_llm=used_llm,
        writer_token=config.llm_token,
        kbase_token=config.kbase_token,
    )

    final_state = execution_workflow.run(analysis_state)
    return final_state


def write_draft_mra(narr_id: int, config: PipelineConfig):
    ws_client = Workspace(token=config.kbase_token)
    ee_client = ExecutionEngine(token=config.kbase_token)
    if config.llm_provider == "cborg":
        writer_llm = "gpt-o1-cborg"
    else:
        writer_llm = "gpt-o1-openai"

    # Create MRA writer
    mra_writer = MraWriterGraph(
        ws_client, ee_client, writer_llm, writer_token=config.llm_token
    )

    # Run the MRA workflow
    mra_writer.run_workflow(narr_id)



def run_pipeline(config: PipelineConfig):
    logging.info(f"provider: {config.llm_provider}")
    logging.info(f"input file: {config.input_file_path}")
    logging.info(f"input data type: {config.input_data_type}")

    # 1. Make a new narrative
    logging.info("making a new narrative")
    ns = NarrativeService(token=config.kbase_token)
    narr_id = ns.create_new_narrative(config.narrative_name)
    logging.info(f"done - created narrative with id {narr_id}")

    # 2. Import the data to it
    logging.info("Importing data object")
    obj_upa = import_data_file(narr_id, config.input_data_params["app_id"], config.input_data_params["params"], config.kbase_token)
    logging.info(f"done got UPA {obj_upa}")

    # 3. Metadata process.
    logging.info("Starting metadata processing")
    meta_context = process_metadata(narr_id, obj_upa, config).get("output")
    logging.info("Done processing metadata and storing abstract cell")
    logging.info(f"Metadata context: {json.dumps(meta_context, indent=4)}")

    # 4. Analysis process.
    logging.info("Starting analysis step")
    analysis_result_state = run_analysis_workflow(narr_id, obj_upa, meta_context, config)
    logging.info("Done with analysis step")
    logging.info(f"Final steps to run: {json.dumps(analysis_result_state, indent=4)}")

    # 5. Crew graph.
    logging.info("Starting app workflow")
    execution_result_state = run_execution_workflow(analysis_result_state, config)
    logging.info("Done with app workflow")
    logging.info(f"Final execution result state: {execution_result_state}")

    # 6. Writeup graph.
    logging.info("Starting writeup process")
    write_draft_mra(narr_id, config)
    logging.info("Done with writeup")


if __name__ == "__main__":
    config = parse_args()
    logging.basicConfig(
        filename=f"llm_annotation_salterns_{config.input_file_path.split('/')[-1]}.log",
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s"
    )
    run_pipeline(config)


"""
poetry run python scripts/full_pipeline.py \
-k $KB_AUTH_TOKEN \
-p cborg \
-l $CBORG_API_KEY \
-f salterns_MAGs/Salt_Pond_MetaGSF2_C_D2_MG_DASTool_bins_concoct_out.17.contigs.fa \
-t assembly
"""
