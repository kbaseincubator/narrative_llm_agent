
import json
import os
from narrative_llm_agent.workflow_graph.state import WorkflowState
from langsmith import Client
from langsmith.evaluation import evaluate
from langsmith.schemas import Run, Example
import uuid
from openevals.llm import create_llm_as_judge
from narrative_llm_agent.config import get_llm
from narrative_llm_agent.workflow_graph.graph_hitl import AnalysisWorkflow

# %%
#load the json, Create a list of narrative IDs from the json
# Load the reference workflow from JSON file
with open('isolates_metadata.json', 'r', encoding='utf-8') as f:
    metadata_json = json.load(f)

# Extract list of narrative IDs
narrative_ids = [isolate['narrative_id'] for isolate in metadata_json['isolates']]
print(f"Narrative IDs: {narrative_ids}")

narrative_descriptions = {}
sequencing_platform = "Illumina NextSeq"
for isolate in metadata_json['isolates']:
    narrative_id = isolate['narrative_id']
    print(narrative_id)
    
    sample_description = f"""The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology: {sequencing_platform}
organism: {isolate['species']} strain {isolate['strain']}
genome type: isolate
number_of_reads: {isolate['number_of_reads']}
I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from {sequencing_platform} for an isolate genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe. Also include a step to annotate and distill assemblies. """
    
    narrative_descriptions[narrative_id] = sample_description


# %%
for item in narrative_descriptions.items():
    print(item[1])

# %%
def load_workflow_json(file_path):
    """
    Load and parse the workflow JSON file
    
    Args:
        file_path (str): Path to the JSON file
    
    Returns:
        dict: Parsed JSON data
    """
    try:
        with open(file_path, 'r') as file:
            workflow_data = json.load(file)
        return workflow_data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

print(narrative_id)
reference_outputs = load_workflow_json(f"{narrative_id}_gt.json")


# %%
#create a list of gts 
# ref=[]
# for item in narrative_descriptions.items():
#     narrative_id = item[0]
#     ref.append(load_workflow_json(f"{narrative_id}_gt.json"))
reference_workflows = {
    narrative_id: load_workflow_json(f"{narrative_id}_gt.json")
    for narrative_id in narrative_descriptions.keys()
}

for item in narrative_descriptions.items():
    print(item)

# %%
# Create LangSmith dataset

client = Client()
uid = uuid.uuid4()
dataset_name = f"KBase Isolate Genome Analysis Workflow Evaluation {uid}"

ds = client.create_dataset(
    dataset_name=dataset_name,
    description=f"Evaluation dataset for KBase isolate genome analysis workflows. "
                f"Based on five Bacillaceae isolates from a degraded wetland environment. "

)


client.create_examples(
    inputs=[{"input": desc} for _, desc in narrative_descriptions.items()],  # List of dicts
    outputs=[{"reference": reference_workflows[narrative_id]} 
             for narrative_id in narrative_descriptions.keys()],
    dataset_id=ds.id,
)
print(f"\n✓ Created dataset: {dataset_name}")
print(f"✓ Dataset ID: {ds.id}")
print(f"✓ DOI: {metadata_json['doi']}")
print(f"\nNarrative IDs in dataset: {narrative_ids}")


# %%
examples = client.list_examples(dataset_id=ds.id)

# View all examples
for example in examples:
    print(example)


# %%
#Analysis evaluation


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



# %%


def wrapped_analysis_correctness(inputs: dict, outputs: dict, reference_outputs: dict):
    """
    Evaluate the correctness of the execution of the steps in the initial state.
    
    Args:
        inputs (dict): The inputs to evaluate.
    
    Returns:
        dict: A dictionary containing the evaluation results.
    """
   
    judge_llm = get_llm("gpt-5-cborg")
    evaluator = create_llm_as_judge(
    prompt=PLANNING_CUSTOM_PROMPT,
    choices=[0.0, 0.5, 1.0],
    judge=judge_llm,
    )
    print("check outputs", outputs)

    eval = evaluator(inputs=inputs,
                          outputs=outputs,
                          reference_outputs=reference_outputs
                          )
    
    return eval

def workflow_analysis_target(inputs:dict) -> dict:
    """Target function that runs your workflow execution"""
    
    # Planning workflow
    workflow = AnalysisWorkflow(
    analyst_llm="claude-sonnet-cborg",
    analyst_token=os.environ.get("CBORG_API_KEY"),
    app_flow_llm="gpt-4.1-cborg",
    app_flow_token=os.environ.get("CBORG_API_KEY"),
    kbase_token=os.environ.get("KB_AUTH_TOKEN"),
)
    print(inputs['input'])
    workflow_state = workflow.run(narrative_id="233415", reads_id="233415/2/1", description=inputs['input'])
    output = workflow_state.get("steps_to_run")
    
    return {"output": json.dumps(output)}

# Run evaluation
experiment_results = client.evaluate(
    workflow_analysis_target,
    data=dataset_name,  
    evaluators=[
        wrapped_analysis_correctness,  
    ],
    experiment_prefix="workflow-analysis-eval",
    max_concurrency=2,
)


# %%
df = experiment_results.to_pandas()
score_eval_b00abb10 = df["feedback.score"].sum()/len(df)

# %%
#save df_new to csv
file_path = f"workflow-analysis-eval-{uid}.csv"
df.to_csv(file_path, index=False)

