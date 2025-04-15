from narrative_llm_agent.agents.workflow import WorkflowRunner


def test_init_ok(mock_llm):
    runner = WorkflowRunner(mock_llm)
    assert runner.role == "KBase workflow runner"
