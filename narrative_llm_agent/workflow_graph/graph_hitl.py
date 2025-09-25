from langgraph.graph import StateGraph, END
from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowState, WorkflowNodes
from narrative_llm_agent.workflow_graph.routers_hitl import next_step_router, analyst_router, post_validation_router

class AnalysisWorkflow:
    """
    Class to handle analysis workflows using LangGraph with human approval.
    """

    def __init__(self, kbase_token:str=None, analyst_llm:str=None, analyst_token:str=None, validator_llm:str=None, validator_token:str=None, app_flow_llm:str=None, app_flow_token:str=None, writer_llm:str=None, writer_token:str=None, embedding_provider:str=None, embedding_provider_token:str=None):
        """Initialize the workflow graph.
        See config.cfg for allowed llm names.
        defaults:
        analyst = gpt-4.1-mini-cborg
        validator = gpt-4.1-mini-cborg
        app_flow = gpt-4.1-mini-cborg
        writer = gpt-4.1-mini-cborg
        embedding_provider = cborg (either cborg or nomic are allowed)
        """
        if analyst_llm is None:
            analyst_llm = "gpt-4.1-mini-cborg"
        if validator_llm is None:
            validator_llm = "gpt-4.1-mini-cborg"
        if app_flow_llm is None:
            app_flow_llm = "gpt-4.1-mini-cborg"
        if writer_llm is None:
            writer_llm = "gpt-4.1-mini-cborg"
        if embedding_provider is None:
            embedding_provider = "cborg"
        self.nodes = WorkflowNodes(analyst_llm, validator_llm, app_flow_llm, writer_llm, embedding_provider, token=kbase_token, analyst_token=analyst_token, validator_token=validator_token, app_flow_token=app_flow_token, writer_token=writer_token, embedding_token=embedding_provider_token)
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the workflow graph for genome analysis with human approval."""
        # Create a new graph
        planning_graph = StateGraph(WorkflowState)
        # Add the nodes
        planning_graph.add_node("analyst", self.nodes.analyst_node)
        planning_graph.add_node("human_approval", self.nodes.human_approval_node)
        planning_graph.add_node("handle_error", self.nodes.handle_error)
        # Define the edges with routing
        planning_graph.add_conditional_edges(
            "analyst",
            analyst_router,
            {
                "human_approval": "human_approval",
                "handle_error": "handle_error"
            }
        )

        planning_graph.add_edge("handle_error", END)
        # Set the entry point
        planning_graph.set_entry_point("analyst")

        # Compile the graph
        return planning_graph.compile()

    def run(self, narrative_id, reads_id, description):
        """
        Run a genome analysis workflow with the given parameters.

        Args:
            narrative_id: The ID of the narrative
            reads_id: The ID of the reads
            description: Description of the analysis to perform

        Returns:
            The final state after workflow completion
        """
        # Initialize the state
        initial_state = {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "steps_to_run": [],
            "completed_steps": [],
            "results": None,
            "error": None,
            "last_executed_step": {},
            "awaiting_approval": False,
            "human_approval_status": None,
            "human_feedback": None,
        }
        # Execute the graph and get the final state
        final_state = self.graph.invoke(initial_state)
        return final_state

    def approve_plan(self, current_state, approved_steps=None):
        """
        Approve the analysis plan and continue workflow.

        Args:
            current_state: The current workflow state
            approved_steps: Optional modified steps, if None uses original plan

        Returns:
            Updated state with approval
        """
        if approved_steps is not None:
            current_state["steps_to_run"] = approved_steps

        current_state["human_approved"] = True
        current_state["awaiting_approval"] = False

        # Continue from human_approval node
        return self.graph.invoke(current_state)

    def reject_plan(self, current_state, feedback=""):
        """
        Reject the analysis plan and provide feedback.

        Args:
            current_state: The current workflow state
            feedback: Feedback for plan modification

        Returns:
            Updated state with rejection
        """
        current_state["human_approved"] = False
        current_state["awaiting_approval"] = False
        current_state["error"] = f"Plan rejected by user. Feedback: {feedback}"

        return current_state

class ExecutionWorkflow:
    """
    Class to handle execution of the analysis workflows after human approval.
    """

    def __init__(self, kbase_token:str=None, analyst_llm:str=None, analyst_token:str=None, validator_llm:str=None, validator_token:str=None, app_flow_llm:str=None, app_flow_token:str=None, writer_llm:str=None, writer_token:str=None, embedding_provider:str=None, embedding_provider_token:str=None):
        """Initialize the workflow graph.
        See config.cfg for allowed llm names.
        defaults:
        analyst = gpt-4.1-mini-cborg
        validator = gpt-4.1-mini-cborg
        app_flow = gpt-4.1-mini-cborg
        writer = gpt-4.1-mini-cborg
        embedding_provider = cborg (either cborg or nomic are allowed)
        """
        if analyst_llm is None:
            analyst_llm = "gpt-4.1-mini-cborg"
        if validator_llm is None:
            validator_llm = "gpt-4.1-mini-cborg"
        if app_flow_llm is None:
            app_flow_llm = "gpt-4.1-mini-cborg"
        if writer_llm is None:
            writer_llm = "gpt-4.1-mini-cborg"
        if embedding_provider is None:
            embedding_provider = "cborg"
        self.nodes = WorkflowNodes(analyst_llm, validator_llm, app_flow_llm, writer_llm, embedding_provider, token=kbase_token, analyst_token=analyst_token, validator_token=validator_token, app_flow_token=app_flow_token, writer_token=writer_token, embedding_token=embedding_provider_token)
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the workflow graph for genome analysis with human approval."""
        # Create a new graph
        genome_graph = StateGraph(WorkflowState)

        # Add the nodes
        genome_graph.add_node("run_workflow_step", self.nodes.app_runner_node)
        genome_graph.add_node("validate_step", self.nodes.workflow_validator_node)
        genome_graph.add_node("handle_error", self.nodes.handle_error)
        genome_graph.add_node("workflow_end", self.nodes.workflow_end)


        # After validation, decide whether to run next step or end
        genome_graph.add_conditional_edges(
            "validate_step",
            post_validation_router,
            {
                "run_workflow_step": "run_workflow_step",
                "workflow_end": "workflow_end",
                "handle_error": "handle_error"
            }
        )

        # After running a workflow step, always go to validator
        genome_graph.add_conditional_edges(
            "run_workflow_step",
            next_step_router,
            {
                "validate_step": "validate_step",
                "workflow_end": "workflow_end",
                "handle_error": "handle_error"
            }
        )

        genome_graph.add_edge("handle_error", END)
        genome_graph.add_edge("workflow_end", END)

        # Set the entry point
        genome_graph.set_entry_point("validate_step")

        # Compile the graph
        return genome_graph.compile()

    def run(self, state) -> WorkflowState:
        """
        Run a genome analysis workflow with the given parameters.

        Args:
            state: The current workflow state after the plan is approved

        Returns:
            The final state after workflow completion
        """

        # Execute the graph and get the final state
        final_state = self.graph.invoke(state)
        return final_state

