from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Define a model for each analysis step
class AnalysisStep(BaseModel):
    Step: int
    Name: str
    App: str
    Description: str
    expect_new_object: bool
    app_id: str
    input_data_object: List[str]
    output_data_object: List[str]
# Define a model for the complete workflow
class AnalysisPipeline(BaseModel):
    steps_to_run: List[AnalysisStep]
class WorkflowDecision(BaseModel):
    continue_as_planned: bool
    reasoning: str
    input_object_upa: Optional[str]
    modified_next_steps: List[AnalysisStep] = []
# Define the state schema
class WorkflowState(BaseModel):
    description: str 
    steps_to_run: Optional[List[Dict[str, Any]]] = None
    last_executed_step: Optional[Dict[str, Any]] = None
    narrative_id: int
    reads_id: str
    step_result: Optional[str] = None
    input_object_upa: Optional[str] = None
    error: Optional[str] = None
    results: Optional[str] = None