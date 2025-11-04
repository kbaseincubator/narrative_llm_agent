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

from typing import Any, Optional
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
from narrative_llm_agent.writer_graph.mra_graph import MraWriterGraph

ASSEMBLY = "assembly"
PE_READS_INT = "pe_reads_interleaved"
PE_READS_NON_INT = "pe_reads_noninterleaved"
SE_READS = "se_reads"

DATA_TYPES = {
    ASSEMBLY: ASSEMBLY,
    PE_READS_INT: "paired-end reads",
    PE_READS_NON_INT: "paired-end reads",
    SE_READS: "single-end reads"
}

SALTERNS_PROMPT = """
The data object is a MAG assembly.

My goal is to perform any relevant quality control on the assembly, then annotate it using a KBase
assembly tool that is useful for MAG data. Quality assurance and control should be done at each step.
I want to end with a taxonomic analysis and prediction for the annotated genome.

The data was gathered from soil samples. I have no other information about the data source or techonology used
to generate it (i.e. sequencing machine, protocol, etc.)
"""

class PipelineConfig(BaseModel):
    kbase_token: str
    llm_provider: str
    llm_token: str
    narrative_name: str
    input_file_path: Optional[str] = None
    input_file_path2: Optional[str] = None
    input_data_type: str
    input_data_params: Optional[dict] = None
    input_upa: Optional[str]
    is_salterns: Optional[bool] = False

def parse_args() -> PipelineConfig:
    """
    Some groups of options.
    Input files are used (along with data type and some parameters) to import a data file from
    the user's staging area.
    UPAs are used to copy an existing data object to the new Narrative.
    These are mutually exclusive! One and only one must be used, this will
    raise a ValueError otherwise.
    """
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
    data_input_group = parser.add_mutually_exclusive_group(required=True)

    data_input_group.add_argument(
        "-f", "--input_file_path", help="staging area file path to data object"
    )

    parser.add_argument(
        "-f2", "--input_file_path2", help="staging area file path to second data object - only for non-interleaved paired-end reads"
    )

    parser.add_argument(
        "-t", "--data_type", help="staging area file data type to import as", required=True
    )
    data_input_group.add_argument(
        "-u", "--upa", help="data object to copy as initial data input"
    )

    parser.add_argument(
        "--salterns", action="store_true", help="treat as salterns MAG input"
    )
    args = parser.parse_args()

    input_params = None
    obj_name = None

    data_type = args.data_type.lower()
    if data_type not in DATA_TYPES:
        raise ValueError(f"-t/--data_type must be one of {DATA_TYPES}")

    if args.input_file_path2:
        if not args.input_file_path:
            raise ValueError("-f/-input_file_path must be provided first with a second file path")
        if data_type != PE_READS_NON_INT:
            raise ValueError("-f2/--input_file_path2 must only be provided with paired-end non-interleaved reads")

    if args.input_file_path:
        obj_name = args.input_file_path.split('/')[-1]
        input_params = data_type_to_params(data_type, args.input_file_path, args.input_file_path2, obj_name)

    if obj_name is None and args.upa is not None:
        ws = Workspace(token=args.kbase_token)
        obj_name = ws.get_object_info(args.upa).name

    narrative_name = f"LLM Agent Annotation for {obj_name}"

    config = PipelineConfig(
        kbase_token=args.kbase_token,
        llm_provider=args.llm_provider,
        llm_token=args.llm_token,
        narrative_name=narrative_name,
        input_file_path=args.input_file_path,
        input_data_type=data_type,
        input_data_params=input_params,
        input_upa=args.upa,
        is_salterns=args.salterns
    )
    return config

def data_type_to_params(data_type: str, file_path: str, file_path2: str|None, file_name: str) -> dict[str, Any]:
    if data_type == ASSEMBLY:
        return {
            "app_id": "kb_uploadmethods/import_fasta_as_assembly_from_staging",
            "params": {
                "staging_file_subdir_path": file_path,
                "assembly_name": file_name + "_assembly",
                "type": "mag",
                "min_contig_length": 500
            }
        }
    elif data_type == PE_READS_INT:
        return {
            "app_id": "kb_uploadmethods/import_fastq_interleaved_as_reads_from_staging",
            "params": {
                "fastq_fwd_staging_file_name": file_path,
                "sequencing_tech": "Unknown",
                "name": file_name + "_reads",
                "single_genome": 1,
                "read_orientation_outward": 0,
                "insert_size_std_dev": None,
                "insert_size_mean": None
            }
        }
    elif data_type == PE_READS_NON_INT:
        if not file_path2:
            raise ValueError("a second file path must be provided for paired-end-non-interleaved reads")
        return {
            "app_id": "kb_uploadmethods/import_fastq_noninterleaved_as_reads_from_staging",
            "params": {
                "fastq_fwd_staging_file_name": file_path,
                "fastq_rev_staging_file_name": file_path2,
                "sequencing_tech": "Unknown",
                "name": file_name + "_reads",
                "single_genome": 1,
                "read_orientation_outward": 0,
                "insert_size_std_dev": None,
                "insert_size_mean": None
            }
        }
    else:
        raise ValueError(f"Unsupported data type '{data_type}'")

def import_data(narr_id: int, config: PipelineConfig) -> str:
    logging.info(f"Starting data import to narrative {narr_id}")
    if config.input_file_path:
        if not config.input_data_params:
            err = "When importing a data file, input_data_params must be present and contain `app_id` and `params` fields"
            logging.error(err)
            raise ValueError(err)
        logging.info("Found data file path - importing data from staging area")
        return import_data_file(narr_id, config.input_data_params["app_id"], config.input_data_params["params"], config.kbase_token)
    elif config.input_upa:
        logging.info("Found existing UPA, copying data object")
        return copy_data_object(narr_id, config.input_upa, config.kbase_token)
    else:
        raise ValueError("Importing data requires either input_file_path or input_upa to be non null in the config")

def copy_data_object(narr_id: int, input_upa: str, token: str) -> str:
    ws = Workspace(token=token)
    logging.info(f"Copying data object {input_upa} to narrative {narr_id}")
    result = ws.copy_object_to_workspace(narr_id, input_upa)
    logging.info(f"Done - created object {result.upa}")
    return result.upa

def import_data_file(narr_id: int, app_id: str, app_params: dict[str, Any], token: str) -> str:
    """
    Imports a data file from the staging service into a narrative and returns the
    generated new object UPA.
    # TODO: update to a bulk import cell later.
    """
    ee = ExecutionEngine(token=token)
    nms = NarrativeMethodStore()
    ws = Workspace(token=token)
    logging.info(f"Starting file import job in narrative {narr_id}: {app_id} with params {json.dumps(app_params)}")
    result = run_job(narr_id, app_id, app_params, ee, nms, ws)
    if result.job_error:
        logging.error(result.job_error)
        logging.error(result.model_dump_json(indent=4))
        raise RuntimeError(result.job_error)
    if len(result.created_objects) > 1:
        logging.error(result.model_dump_json(indent=4))
        raise RuntimeError(f"Unexpected import results: {result}")
    new_upa = result.created_objects[0].object_upa
    logging.info(f"Done - created object {new_upa}")
    return new_upa

def process_metadata(narr_id: int, obj_upa: str, config: PipelineConfig):
    ws = Workspace(token=config.kbase_token)
    obj_info = ws.get_object_info(obj_upa)
    meta_prompt = f"""I am working with narrative id {narr_id} and object UPA {obj_upa}.
This object has the registered metadata dictionary: {obj_info.metadata}.
"""

    if config.is_salterns:
        meta_prompt += SALTERNS_PROMPT

    meta_prompt += """
Infer any other metadata that you can from the given metadata dictionary. If none is available,
that is fine, too. You must not ask questions of a human user.
"""

    if config.llm_provider == "cborg":
        used_llm = "gpt-5-cborg"
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
        used_llm = "claude-sonnet-cborg-high"
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
The user has uploaded {DATA_TYPES[config.input_data_type]} data into the narrative.
I want you to generate an analysis plan for processing the uploaded {DATA_TYPES[config.input_data_type]} into an annotated genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe.

NEVER suggest an app from the NarrativeViewers module. This includes any app with "NarrativeViewers" in its app_id.

NEVER suggest the app with id "RAST_SDK/annotate_contigset". If you want to suggest a RAST app for assembly annotation, suggest
"RAST_SDK/annotate_genome_assembly" instead.

Here is additional context: {meta_context}
"""

    # Run the planning phase only
    return workflow.run(
        narrative_id=narr_id, reads_id=obj_upa, description=description
    )


def run_execution_workflow(analysis_state: dict[str, Any], config: PipelineConfig) -> dict[str, Any]:
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
        writer_llm = "gpt-5-cborg"
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
    obj_upa = import_data(narr_id, config)
    # obj_upa = import_data(narr_id, config.input_data_params["app_id"], config.input_data_params["params"], config.kbase_token)
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
        filename="llm_genome_annotation.log",
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s"
    )
    run_pipeline(config)


"""
poetry run python scripts/full_pipeline.py \
-k $KB_AUTH_TOKEN \
-p cborg \
-l $CBORG_API_KEY \
-f salterns_MAGs/Salt_Pond_MetaG_R2A_A_D2_MG_DASTool_bins_concoct_out.10.contigs.fa \
-t assembly
"""

"""
poetry run python scripts/full_pipeline.py \
-k $KB_AUTH_TOKEN \
-p cborg \
-l $CBORG_API_KEY \
-u 232591/2/1 \
-t assembly
"""


"""
poetry run python scripts/full_pipeline.py \
-k $KB_AUTH_TOKEN \
-p cborg \
-l $CBORG_API_KEY \
-u 172257/37/1 \
-t pe_reads_interleaved
"""
