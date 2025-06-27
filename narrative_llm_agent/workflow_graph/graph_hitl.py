from langgraph.graph import StateGraph, END
from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowState, WorkflowNodes
from langgraph.checkpoint.memory import MemorySaver
from narrative_llm_agent.workflow_graph.routers_hitl import next_step_router, analyst_router, post_validation_router, human_approval_router

class AnalysisWorkflow:
    """
    Class to handle analysis workflows using LangGraph.
    """

    def __init__(self, token:str=None, analyst_llm:str=None, validator_llm:str=None, app_flow_llm:str=None, writer_llm:str=None, embedding_provider:str=None, approval_handler=None):
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
        self.nodes = WorkflowNodes(analyst_llm, validator_llm, app_flow_llm, writer_llm, embedding_provider, token=token, approval_handler=approval_handler)
        self.memory = MemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the workflow graph for genome analysis."""
        # Create a new graph
        genome_graph = StateGraph(WorkflowState)

        # Add the nodes
        genome_graph.add_node("analyst", self.nodes.analyst_node)
        genome_graph.add_node("human_approval", self.nodes.human_approval_node)
        genome_graph.add_node("run_workflow_step", self.nodes.app_runner_node)
        genome_graph.add_node("validate_step", self.nodes.workflow_validator_node)
        genome_graph.add_node("handle_error", self.nodes.handle_error)
        genome_graph.add_node("workflow_end", self.nodes.workflow_end)

        # Define the edges with routing
        genome_graph.add_conditional_edges(
            "analyst",
            analyst_router,
            {
                "human_approval": "human_approval",  # Route to human approval after analyst
                "handle_error": "handle_error"
            }
        )
        
        # After human approval, decide next step
        genome_graph.add_conditional_edges(
            "human_approval",
            human_approval_router,
            {
                "validate_step": "validate_step",  # If approved, proceed to validation
                "analyst": "analyst",  # If rejected, go back to analyst for revision
                "workflow_end": "workflow_end",  # If cancelled, end workflow
                "handle_error": "handle_error"
            }
        )
        
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
        genome_graph.set_entry_point("analyst")

        # Compile the graph
        return genome_graph.compile(checkpointer=self.memory)

    def run(self, narrative_id, reads_id, description, thread_id=None):
        """
        Run a genome analysis workflow.
        
        Args:
            narrative_id: The ID of the narrative
            reads_id: The ID of the reads
            description: Description of the analysis to perform
            thread_id: Optional thread ID for workflow tracking
        
        Returns:
            The final state after workflow completion
        """
        import uuid
        
        if thread_id is None:
            thread_id = str(uuid.uuid4())
        
        config = {"thread_id": thread_id}
        
        # Initialize the state
        initial_state = {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "steps_to_run": [],
            "completed_steps": [],
            "last_executed_step": {},
            "input_object_upa": None,
            "last_data_object_upa": None,
            "human_approval_status": None,
            "human_feedback": None,
            "error": None,
            "results": None
        }

        # Execute the graph - this handles interrupts automatically
        final_state = self.graph.invoke(initial_state, config=config)
        return final_state