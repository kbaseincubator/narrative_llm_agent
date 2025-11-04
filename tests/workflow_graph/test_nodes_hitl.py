from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowNodes, WorkflowState
from narrative_llm_agent.agents.analyst_lang import AnalysisSteps
import pytest
from unittest.mock import Mock, patch

VALID_LLM_NAME = "gpt-4.1-mini-cborg"


@pytest.fixture
def mock_llm_factory():
    """Mock the LLM factory function."""
    with patch('narrative_llm_agent.workflow_graph.nodes.get_llm') as mock_get_llm:
        mock_get_llm.return_value = Mock()
        yield mock_get_llm


@pytest.fixture
def workflow_nodes(mock_llm_factory):
    """Create a WorkflowNodes instance with a mock token."""
    return WorkflowNodes(VALID_LLM_NAME, VALID_LLM_NAME, VALID_LLM_NAME, VALID_LLM_NAME, "cborg", token="mock_token")


@pytest.fixture(scope="module")
def base_wf_state():
    """A convenience fixture that provides a bare-bones WorkflowState
    model that can be filled out for individual tests."""
    return WorkflowState(
        description="",
        steps_to_run=[],
        last_executed_step={},
        completed_steps = [],
        narrative_id=0,
        reads_id="",
    )


def test_init_wf_nodes():
    # TODO: this should iterate over combinations including None
    llm_names = ["llm1", "llm2", "llm3", "llm4", "some_embedder"]
    llm_tokens = {
        "analyst_token": "llm_key1",
        "validator_token": "llm_key2",
        "app_flow_token": "llm_key3",
        "writer_token": "llm_key4",
        "embedding_token": "embedding_key"
    }
    kbase_token = "user_kbase_token"

    nodes = WorkflowNodes(
        *llm_names,
        **llm_tokens,
        token=kbase_token,
    )

    assert isinstance(nodes, WorkflowNodes)


def test_init_wf_nodes_token_fail():
    with pytest.raises(ValueError, match="KBase auth token must be provided"):
        WorkflowNodes("llm1", "llm2", "llm3", "llm4", "embed")


class TestWorkflowValidatorNode:
    def _validate_prompt(self, prompt: str):
        pass

    def _make_current_state(self, base_wf_state: WorkflowState, obj_upa: str, narrative_id: int):
        return base_wf_state.model_copy(
            update={
                "steps_to_run": [{
                    "step": 2,
                    "name": "Assess Genome Quality with CheckM",
                    "app": "Assess Genome Quality with CheckM - v1.0.18",
                    "description": "Estimate genome completeness and contamination levels using CheckM lineage workflow. This is essential for MAG quality assessment in MRA papers and provides completeness percentage, contamination percentage, strain heterogeneity, and lineage-specific marker gene analysis. High-quality MAGs should have >90% completeness and <5% contamination.",
                    "expect_new_object": False,
                    "app_id": "kb_Msuite/run_checkM_lineage_wf"
                }],
                "last_executed_step": {
                    "step": 1,
                    "name": "Assess Quality of Assemblies with QUAST",
                    "app": "Assess Quality of Assemblies with QUAST - v4.4",
                    "description": "Generate comprehensive assembly statistics required for MRA paper including total assembly size, number of contigs, N50 value, L50 value, largest contig length, and GC content. This provides the standard assembly quality metrics required in genome announcements.",
                    "expect_new_object": False,
                    "app_id": "kb_quast/run_QUAST_app"
                },
                "completed_steps": [{
                    "step": 1,
                    "name": "Assess Quality of Assemblies with QUAST",
                    "app": "Assess Quality of Assemblies with QUAST - v4.4",
                    "description": "Generate comprehensive assembly statistics required for MRA paper including total assembly size, number of contigs, N50 value, L50 value, largest contig length, and GC content. This provides the standard assembly quality metrics required in genome announcements.",
                    "expect_new_object": False,
                    "app_id": "kb_quast/run_QUAST_app"
                }],
                "input_object_upa": obj_upa,
                "last_data_object_upa": obj_upa,
                "reads_id": obj_upa,
                "step_result": {
                    "job_id": "12345",
                    "job_status": "success",
                    "job_error": None,
                    "created_objects": [],
                    "narrative_id": narrative_id
                },
                "narrative_id": narrative_id
            }
        )

    def test_workflow_validator_node_done(self, workflow_nodes: WorkflowNodes, base_wf_state: WorkflowState):
        state = base_wf_state.model_copy()
        next_state = workflow_nodes.workflow_validator_node(state)
        assert next_state.results == "Workflow complete. All steps were successfully executed."
        assert next_state.error is None

    def test_workflow_validator_node_continue(self, mocker, workflow_nodes: WorkflowNodes, base_wf_state: WorkflowState, mock_validator_agent):
        obj_upa = "11/22/33"
        narrative_id = 123

        # Patch the WorkflowValidatorAgent with our mock
        mocker.patch(
            "narrative_llm_agent.workflow_graph.nodes_hitl.WorkflowValidatorAgent",
            return_value=mock_validator_agent
        )

        state = self._make_current_state(base_wf_state, obj_upa, narrative_id)

        next_state = workflow_nodes.workflow_validator_node(state)
        assert next_state.validation_reasoning == "Test validation passed"
        assert next_state.input_object_upa == obj_upa


    def test_workflow_validator_node_revise(self, mocker, workflow_nodes: WorkflowNodes, base_wf_state: WorkflowState, mock_validator_agent_factory):
        """Test when the validator revises the workflow steps."""
        obj_upa = "11/22/33"
        narrative_id = 123

        # Create a revised step to be returned by the validator
        revised_step = AnalysisSteps(
            step=2,
            name="Alternative Analysis Step",
            app="Alternative App",
            description="An alternative approach to the original step",
            expect_new_object=True,
            app_id="alt/app"
        )

        # Create a mock validator that revises the steps
        mock_agent = mock_validator_agent_factory(
            continue_as_planned=False,
            reasoning="Original approach not suitable, revised steps provided",
            input_object_upa=obj_upa,
            modified_next_steps=[revised_step]
        )

        mocker.patch(
            "narrative_llm_agent.workflow_graph.nodes_hitl.WorkflowValidatorAgent",
            return_value=mock_agent
        )

        state = self._make_current_state(base_wf_state, obj_upa, narrative_id)

        next_state = workflow_nodes.workflow_validator_node(state)
        assert next_state.steps_to_run[0]["name"] == "Alternative Analysis Step"
        assert next_state.validation_reasoning == "Original approach not suitable, revised steps provided"

    def test_workflow_validator_node_end(self, mocker, mock_validator_agent_factory, workflow_nodes: WorkflowNodes, base_wf_state: WorkflowState):
        """Test when the validator says the run should end."""
        obj_upa = "11/22/33"
        narrative_id = 123

        # Create a mock validator that revises the steps
        mock_agent = mock_validator_agent_factory(
            continue_as_planned=False,
            reasoning="Key app unavailable, stop running",
            input_object_upa=obj_upa,
            modified_next_steps=[]
        )

        mocker.patch(
            "narrative_llm_agent.workflow_graph.nodes_hitl.WorkflowValidatorAgent",
            return_value=mock_agent
        )

        state = base_wf_state.model_copy(
            update={
                "steps_to_run": [{
                    "step": 2,
                    "name": "Assess Genome Quality with CheckM",
                    "app": "Assess Genome Quality with CheckM - v1.0.18",
                    "description": "Original assessment approach",
                    "expect_new_object": False,
                    "app_id": "kb_Msuite/run_checkM_lineage_wf"
                }],
                "last_executed_step": {
                    "step": 1,
                    "name": "Assess Quality of Assemblies with QUAST",
                    "app": "Assess Quality of Assemblies with QUAST - v4.4",
                    "description": "Assembly QC",
                    "expect_new_object": False,
                    "app_id": "kb_quast/run_QUAST_app"
                },
                "completed_steps": [],
                "input_object_upa": obj_upa,
                "last_data_object_upa": obj_upa,
                "reads_id": obj_upa,
                "step_result": {
                    "job_id": "12345",
                    "job_status": "success",
                    "job_error": None,
                    "created_objects": [],
                    "narrative_id": narrative_id
                },
                "narrative_id": narrative_id
            }
        )
        next_state = workflow_nodes.workflow_validator_node(state)
        assert next_state.steps_to_run == []
        assert next_state.validation_reasoning == "Key app unavailable, stop running"

    def test_workflow_validator_node_error(self, mocker, mock_validator_agent_factory, workflow_nodes: WorkflowNodes, base_wf_state: WorkflowState):
        """Test when the validator encounters an error."""
        obj_upa = "11/22/33"
        narrative_id = 123

        # Create a mock validator that revises the steps
        mock_agent = mock_validator_agent_factory(
            raise_exception=True
        )

        mocker.patch(
            "narrative_llm_agent.workflow_graph.nodes_hitl.WorkflowValidatorAgent",
            return_value=mock_agent
        )

        state = base_wf_state.model_copy(
            update={
                "steps_to_run": [{
                    "step": 2,
                    "name": "Assess Genome Quality with CheckM",
                    "app": "Assess Genome Quality with CheckM - v1.0.18",
                    "description": "Original assessment approach",
                    "expect_new_object": False,
                    "app_id": "kb_Msuite/run_checkM_lineage_wf"
                }],
                "last_executed_step": {
                    "step": 1,
                    "name": "Assess Quality of Assemblies with QUAST",
                    "app": "Assess Quality of Assemblies with QUAST - v4.4",
                    "description": "Assembly QC",
                    "expect_new_object": False,
                    "app_id": "kb_quast/run_QUAST_app"
                },
                "completed_steps": [],
                "input_object_upa": obj_upa,
                "last_data_object_upa": obj_upa,
                "reads_id": obj_upa,
                "step_result": {
                    "job_id": "12345",
                    "job_status": "success",
                    "job_error": None,
                    "created_objects": [],
                    "narrative_id": narrative_id
                },
                "narrative_id": narrative_id
            }
        )
        next_state = workflow_nodes.workflow_validator_node(state)
        assert "Some stuff failed with the LLM!" in next_state.error
