"""
The script expects KB_AUTH_TOKEN and CBORG_API_KEY to be available (typically
via a .env file at the repo root).
"""
import argparse
import json
import os
import re
import uuid
from pathlib import Path

import dotenv
from langsmith import Client
from openevals.llm import create_llm_as_judge

from narrative_llm_agent.config import get_llm
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.objects.narrative import AppCell
from narrative_llm_agent.tools.narrative_tools import get_narrative_from_wsid
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.workflow_graph.graph_hitl import AnalysisWorkflow

PLANNING_CUSTOM_PROMPT = """
You are an expert bioinformatics workflow evaluator specializing in KBase analysis plans. Your task is to evaluate how well a generated analysis plan matches the expected workflow for genomic/metagenomic data processing.

<Rubric>
A high-quality analysis plan should:
- Include the correct sequence of analysis steps in logical order
- Use appropriate KBase apps or functionally equivalent alternatives
- Have accurate descriptions of what each step accomplishes
- Cover all necessary stages of the analysis workflow
- Maintain scientific rigor and best practices

When evaluating, consider:
- **Step Coverage**: Are all essential analysis steps present?
- **App Selection**: Are the KBase apps appropriate? (Note: functionally equivalent apps are acceptable, e.g., RAST vs Prokka for annotation, megahit vs SPAdes for assembly)
- **Logical Flow**: Do steps follow a scientifically sound order?
- **Completeness**: Are critical quality control and validation steps included?
- **Accuracy**: Are step descriptions technically correct?

Scoring Criteria:
- **Excellent (0.9-1.0)**: Plan includes all essential steps with appropriate or equivalent apps and correct order. Minor differences in app choices are acceptable if functionally equivalent.

- **Good (0.7-0.89)**: Plan covers most essential steps with mostly appropriate apps. May have minor gaps in coverage or slight ordering issues, but overall workflow is sound.

- **Adequate (0.5-0.69)**: Plan includes core steps but missing some important quality control or validation steps. Apps are generally appropriate but may have some suboptimal choices. 
- **Poor (0.3-0.49)**: Plan is incomplete, missing several important steps. Some inappropriate app selections. Workflow order may have issues. Descriptions contain inaccuracies.

- **Very Poor (0.1-0.29)**: Plan is severely incomplete or incorrect. Many inappropriate apps. Major gaps in workflow logic.

- **Incorrect (0.0)**: Plan is fundamentally flawed, missing most essential steps, or doesn't utilize KBase apps appropriately.
</Rubric>

<Instructions>
1. Compare the output plan to the reference workflow step-by-step
2. Identify which steps are present, missing, or incorrect
3. Evaluate app choices, accepting functionally equivalent alternatives (examples below)
4. Assess the logical flow and completeness of the workflow
5. Provide a score based on the rubric above
6. In your reasoning, briefly note:
   - Major steps correctly included
   - Any important missing steps
   - Appropriate app substitutions identified
   - Significant errors or omissions
7. It is okay to not have multiple apps for annotation or assemble as long as the chosen app is appropriate.
</Instructions>

<Functionally Equivalent Apps>
These app substitutions should NOT be penalized:
- Assembly: SPAdes ↔ megahit ↔ metaSPAdes
- Annotation: Prokka ↔ RAST ↔ PGAP
- Quality Assessment: FastQC ↔ MultiQC
- Trimming: Trimmomatic ↔ fastp ↔ Cutadapt
- Taxonomic Classification: GTDB-Tk ↔ Kraken2 ↔ Kaiju (context-dependent)
- Completeness: CheckM ↔ BUSCO
</Functionally Equivalent Apps>

<input>
User Request/Description: {inputs}
</input>

<output>
Generated Analysis Plan: {outputs}
</output>

<reference_outputs>
Expected Workflow (Ground Truth): {reference_outputs}
</reference_outputs>

Now evaluate the generated plan against the reference workflow. Provide:
1. A brief analysis (2-3 sentences) of strengths and weaknesses
2. Your numerical score from the rubric
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run workflow evaluation for isolates metadata JSON.",
    )
    parser.add_argument(
        "--metadata",
        required=True,
        type=Path,
        help="Path to isolates metadata JSON (already created).",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("."),
        type=Path,
        help="Directory to write GT JSON files and evaluation CSV.",
    )
    parser.add_argument(
        "--experiment-prefix",
        default="workflow-analysis-eval",
        help="Prefix for the LangSmith experiment name.",
    )
    parser.add_argument(
        "--judge-llm",
        default="gpt-5-cborg",
        help="LLM used for judging; used in the CSV filename.",
    )
    parser.add_argument(
        "--analyst-llm",
        default="claude-sonnet-cborg",
        help="LLM used by the analysis workflow planner.",
    )
    parser.add_argument(
        "--app-flow-llm",
        default="gpt-4.1-cborg",
        help="LLM used for app selection in the workflow planner.",
    )
    parser.add_argument(
        "--workflow-narrative-id",
        default="233415",
        help="Narrative ID passed to AnalysisWorkflow.run.",
    )
    parser.add_argument(
        "--reads-id",
        default="233415/2/1",
        help="Reads object ID passed to AnalysisWorkflow.run.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    """Make a filesystem-friendly string."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")


def load_metadata(metadata_path: Path) -> dict:
    with metadata_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_descriptions(metadata: dict, sequencing_platform: str = "Illumina NextSeq") -> dict:
    """Build narrative descriptions keyed by narrative id."""
    descriptions = {}
    for isolate in metadata["isolates"]:
        narrative_id = str(isolate["narrative_id"])
        sample_description = (
            "The user has uploaded paired-end sequencing reads into the narrative. "
            "Here is the metadata for the reads:\n"
            f"sequencing_technology: {sequencing_platform}\n"
            f"organism: {isolate['species']} strain {isolate['strain']}\n"
            "genome type: isolate\n"
            f"number_of_reads: {isolate['number_of_reads']}\n"
            f"I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from {sequencing_platform} for an isolate genome using KBase apps.\n"
            "The goal is to have a complete annotated genome and classify the microbe. Also include a step to annotate and distill assemblies. "
        )
        descriptions[narrative_id] = sample_description
    return descriptions


def create_workflow_json(narrative_id: int, workspace: Workspace, output_dir: Path) -> Path:
    """Fetch a narrative and emit a simplified ground truth workflow JSON."""
    narrative = get_narrative_from_wsid(
        process_tool_input(narrative_id, "narrative_id"),
        workspace,
    )

    app_cells_data = {}
    step_counter = 1
    for cell in narrative.cells:
        if isinstance(cell, AppCell):
            app_entry = {"app_name": cell.app_name, "app_id": cell.app_id}
            app_cells_data[f"step{step_counter}"] = app_entry
            step_counter += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{narrative_id}_gt.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(app_cells_data, f, indent=2)

    return output_path


def load_workflow_json(file_path: Path) -> dict:
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[3]
    dotenv.load_dotenv(repo_root / ".env")

    metadata = load_metadata(args.metadata)
    narrative_descriptions = build_descriptions(metadata)
    #narrative_ids = list(narrative_descriptions.keys())
    # Extract list of narrative IDs
    narrative_ids = [isolate['narrative_id'] for isolate in metadata['isolates']]

    print(f"Narrative IDs: {narrative_ids}")
    workspace = Workspace(token=os.getenv("KB_AUTH_TOKEN"))

    # Create/refresh ground truth workflow files for each narrative.
    gt_paths = []
    for narrative_id in narrative_ids:
        gt_paths.append(create_workflow_json(int(narrative_id), workspace, args.output_dir))

    reference_workflows = {
        narrative_id: load_workflow_json(args.output_dir / f"{narrative_id}_gt.json")
        for narrative_id in narrative_ids
    }

    client = Client()
    uid = uuid.uuid4().hex[:8]
    dataset_name = f"KBase Isolate Genome Analysis Workflow Evaluation {uid}"

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=(
            "Evaluation dataset for KBase isolate genome analysis workflows. "
            "Based on isolates metadata provided to the script."
        ),
    )

    client.create_examples(
        inputs=[{"input": desc} for _, desc in narrative_descriptions.items()],
        outputs=[{"reference": reference_workflows[narrative_id]} for narrative_id in narrative_ids],
        dataset_id=dataset.id,
    )

    def wrapped_analysis_correctness(inputs: dict, outputs: dict, reference_outputs: dict):
        judge_llm = get_llm(args.judge_llm)
        evaluator = create_llm_as_judge(
            prompt=PLANNING_CUSTOM_PROMPT,
            choices=[0.0,0.1,0.2,0.3,0.4 0.5,0.6,0.7,0.8,0.9,1.0],
            judge=judge_llm,
        )
        return evaluator(inputs=inputs, outputs=outputs, reference_outputs=reference_outputs)

    def workflow_analysis_target(inputs: dict) -> dict:
        workflow = AnalysisWorkflow(
            analyst_llm=args.analyst_llm,
            analyst_token=os.environ.get("CBORG_API_KEY"),
            app_flow_llm=args.app_flow_llm,
            app_flow_token=os.environ.get("CBORG_API_KEY"),
            kbase_token=os.environ.get("KB_AUTH_TOKEN"),
        )
        workflow_state = workflow.run(
            narrative_id=args.workflow_narrative_id,
            reads_id=args.reads_id,
            description=inputs["input"],
        )
        output = workflow_state.get("steps_to_run")
        return {"output": json.dumps(output)}

    experiment_results = client.evaluate(
        workflow_analysis_target,
        data=dataset_name,
        evaluators=[wrapped_analysis_correctness],
        experiment_prefix=args.experiment_prefix,
        max_concurrency=2,
    )

    df = experiment_results.to_pandas()
    csv_name = (
        f"{slugify(args.experiment_prefix)}-"
        f"{slugify(args.judge_llm)}-"
        f"{slugify(args.analyst_llm)}-"
        f"{uid}.csv"
    )
    csv_path = args.output_dir / csv_name
    df.to_csv(csv_path, index=False)

    print(f"✓ Created dataset: {dataset_name}")
    print(f"✓ Saved evaluation CSV to {csv_path}")
    print(f"Narrative IDs: {narrative_ids}")
    print(f"Metadata DOI: {metadata.get('doi', 'N/A')}")


if __name__ == "__main__":
    main()


"""
python evalaute_planning.py \                            
  --metadata ~/LLM/narrative_agent_test/notebooks/evaluation/isolates_metadata.json \
  --output-dir ~/LLM/narrative_agent_test/notebooks/evaluation \
  --experiment-prefix workflow-analysis-eval \
  --judge-llm gpt-5-cborg \
  --analyst-llm claude-sonnet-cborg
"""
