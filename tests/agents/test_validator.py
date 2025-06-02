from narrative_llm_agent.agents.validator import WorkflowValidatorAgent
from unittest.mock import MagicMock

def test_init_ok():
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm  # if bind_tools is called
    wa = WorkflowValidatorAgent(llm=mock_llm)
    assert wa.role == "You are a workflow validator, responsible for analyzing app run results and determining next steps."
    assert wa.goal == "Ensure that each step in a computational biology workflow produces expected results and that subsequent steps are appropriate."
    assert wa.backstory.startswith("You are an experienced computational biologist")
    assert len(wa.agent.tools) == 2