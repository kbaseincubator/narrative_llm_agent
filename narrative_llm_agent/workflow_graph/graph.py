from langgraph.graph import StateGraph, END
from narrative_llm_agent.workflow_graph.nodes import WorkflowState, WorkflowNodes
from narrative_llm_agent.workflow_graph.routers import next_step_router, analyst_router, post_validation_router

class AnalysisWorkflow:
    """
    Class to handle analysis workflows using LangGraph.
    """
    
    def __init__(self,token=None):
        """Initialize the workflow graph."""
        self.nodes = WorkflowNodes(token=token)
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the workflow graph for genome analysis."""
        # Create a new graph
        genome_graph = StateGraph(WorkflowState)
        
        # Add the nodes
        genome_graph.add_node("analyst", self.nodes.analyst_node)
        genome_graph.add_node("run_workflow_step", self.nodes.workflow_runner_node)
        genome_graph.add_node("validate_step", self.nodes.workflow_validator_node)
        genome_graph.add_node("handle_error", self.nodes.handle_error)
        genome_graph.add_node("workflow_end", self.nodes.workflow_end)
        
        # Define the edges with routing
        genome_graph.add_conditional_edges(
            "analyst",
            analyst_router,
            {
                "validate_step": "validate_step",
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
        return genome_graph.compile()

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
            "analysis_plan": None,
            "steps_to_run": None,
            "results": None,
            "error": None,
            "last_executed_step": {}  # Initialize with empty dict to prevent KeyError
        }
        
        # Execute the graph and get the final state
        final_state = self.graph.invoke(initial_state)
        return final_state