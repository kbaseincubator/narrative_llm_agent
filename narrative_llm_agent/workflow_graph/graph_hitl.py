from langgraph.graph import StateGraph, END
from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowState, WorkflowNodes
from narrative_llm_agent.workflow_graph.routers_hitl import next_step_router, analyst_router, post_validation_router
import time
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('workflow.log')
    ]
)

# Create workflow-specific logger
workflow_logger = logging.getLogger('WorkflowExecution')

class WorkflowCallback:
    """Custom callback to log workflow execution"""
    
    def __init__(self, logger):
        self.logger = logger
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        self.logger.info(f"WORKFLOW STARTED with inputs: {list(inputs.keys())}")
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        self.logger.info(f"WORKFLOW COMPLETED")
    
    def on_chain_error(self, error: Exception, **kwargs) -> None:
        self.logger.error(f"WORKFLOW ERROR: {error}")

def log_node_execution(node_name: str, state: WorkflowState, result: WorkflowState = None):
    """Helper function to log node execution details"""
    workflow_logger.info(f"NODE: {node_name}")
    workflow_logger.info(f"Input - Steps remaining: {len(state.steps_to_run) if state.steps_to_run else 0}")
    workflow_logger.info(f"Input - Awaiting approval: {state.awaiting_approval}")
    workflow_logger.info(f"Input - Error: {state.error}")
    workflow_logger.info(f"Input - Results: {state.results}")
    
    if result:
        workflow_logger.info(f"Output - Steps remaining: {len(result.steps_to_run) if result.steps_to_run else 0}")
        workflow_logger.info(f"Output - Awaiting approval: {result.awaiting_approval}")
        workflow_logger.info(f"Output - Error: {result.error}")
        workflow_logger.info(f"Output - Results: {result.results}")

def log_router_decision(router_name: str, state: WorkflowState, decision: str):
    """Helper function to log router decisions"""
    workflow_logger.info(f"ROUTER: {router_name}")
    workflow_logger.info(f"State - Steps remaining: {len(state.steps_to_run) if state.steps_to_run else 0}")
    workflow_logger.info(f"State - Error: {state.error}")
    workflow_logger.info(f"State - Awaiting approval: {state.awaiting_approval}")
    workflow_logger.info(f"DECISION: {decision}")

class AnalysisWorkflow:
    """
    Class to handle analysis workflows using LangGraph with human approval.
    """

    def __init__(self, kbase_token:str=None, analyst_llm:str=None, analyst_token:str=None, validator_llm:str=None, validator_token:str=None, app_flow_llm:str=None, app_flow_token:str=None, writer_llm:str=None, writer_token:str=None, embedding_provider:str=None, embedding_provider_token:str=None):
        """Initialize the workflow graph with logging enabled."""
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
        self.callback = WorkflowCallback(workflow_logger)

    def _create_logged_node(self, node_name: str, node_func):
        """Wrap a node function with logging"""
        def logged_node(state: WorkflowState):
            workflow_logger.info(f"ENTERING: {node_name}")
            log_node_execution(node_name, state)
            
            result = node_func(state)
            
            workflow_logger.info(f"EXITING: {node_name}")
            log_node_execution(node_name, state, result)
            
            return result
        return logged_node
    def _create_logged_router(self, router_name: str, router_func):
        """Wrap a router function with logging"""
        def logged_router(state: WorkflowState):
            decision = router_func(state)
            workflow_logger.info(f"ROUTER DECISION: {router_name} -> '{decision}'")
            log_router_decision(router_name, state, decision)
            return decision
        return logged_router
    def _build_graph(self):
        """Build the workflow graph for genome analysis with human approval."""
        # Create a new graph
        planning_graph = StateGraph(WorkflowState)
        
        # Add nodes with logging wrappers
        planning_graph.add_node("analyst", self._create_logged_node("analyst", self.nodes.analyst_node))
        planning_graph.add_node("human_approval", self._create_logged_node("human_approval", self.nodes.human_approval_node))
        planning_graph.add_node("handle_error", self._create_logged_node("handle_error", self.nodes.handle_error))
        
        # Define the edges with logging wrappers for routers
        planning_graph.add_conditional_edges(
            "analyst",
            self._create_logged_router("analyst_router", analyst_router),
            {
                "human_approval": "human_approval",
                "handle_error": "handle_error"
            }
        )

        planning_graph.add_edge("handle_error", END)
        planning_graph.add_edge("human_approval", END)
        planning_graph.set_entry_point("analyst")

        return planning_graph.compile()

    def run(self, narrative_id, reads_id, description):
        """Run analysis workflow with logging."""
        workflow_logger.info(f"🚀 STARTING ANALYSIS WORKFLOW")
        workflow_logger.info(f"   📊 Narrative ID: {narrative_id}")
        workflow_logger.info(f"   📊 Reads ID: {reads_id}")
        workflow_logger.info(f"   📊 Description: {description[:100]}...")
        
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
        
        final_state = self.graph.invoke(initial_state)
        
        workflow_logger.info(f"ANALYSIS WORKFLOW COMPLETED")
        workflow_logger.info(f"Final Steps: {len(final_state.get('steps_to_run', []))}")
        workflow_logger.info(f"Final Error: {final_state.get('error')}")
        workflow_logger.info(f"Final Results: {final_state.get('results')}")
        
        return final_state

    def approve_plan(self, current_state, approved_steps=None):
        """Approve the analysis plan and continue workflow with logging."""
        workflow_logger.info(f"PLAN APPROVED")
        if approved_steps is not None:
            workflow_logger.info(f"Modified steps provided: {len(approved_steps)}")
            current_state["steps_to_run"] = approved_steps

        current_state["human_approved"] = True
        current_state["awaiting_approval"] = False

        return self.graph.invoke(current_state)

    def reject_plan(self, current_state, feedback=""):
        """Reject the analysis plan with logging."""
        workflow_logger.info(f"PLAN REJECTED")
        workflow_logger.info(f"Feedback: {feedback}")
        
        current_state["human_approved"] = False
        current_state["awaiting_approval"] = False
        current_state["error"] = f"Plan rejected by user. Feedback: {feedback}"

        return current_state

class ExecutionWorkflow:
    """Class to handle execution of the analysis workflows after human approval."""

    def __init__(self, kbase_token:str=None, analyst_llm:str=None, analyst_token:str=None, validator_llm:str=None, validator_token:str=None, app_flow_llm:str=None, app_flow_token:str=None, writer_llm:str=None, writer_token:str=None, embedding_provider:str=None, embedding_provider_token:str=None):
        """Initialize the execution workflow with logging enabled."""
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

    def _create_logged_node(self, node_name: str, node_func):
        """Wrap a node function with logging"""
        def logged_node(state: WorkflowState):
            workflow_logger.info(f"🔵 ENTERING NODE: {node_name}")
            log_node_execution(node_name, state)
            
            result = node_func(state)
            
            workflow_logger.info(f"🟢 EXITING NODE: {node_name}")
            log_node_execution(node_name, state, result)
            
            return result
        return logged_node
    def _create_logged_router(self, router_name: str, router_func):
        """Wrap a router function with logging"""
        def logged_router(state: WorkflowState):
            decision = router_func(state)
            log_router_decision(router_name, state, decision)
            return decision
        return logged_router
    
    def _build_graph(self):
        """Build the workflow graph for with logging."""
        genome_graph = StateGraph(WorkflowState)

        # Add nodes with logging
        genome_graph.add_node("run_workflow_step", self._create_logged_node("run_workflow_step", self.nodes.app_runner_node))
        genome_graph.add_node("validate_step", self._create_logged_node("validate_step", self.nodes.workflow_validator_node))
        genome_graph.add_node("handle_error", self._create_logged_node("handle_error", self.nodes.handle_error))
        genome_graph.add_node("workflow_end", self._create_logged_node("workflow_end", self.nodes.workflow_end))

        # Add conditional edges with logging
        genome_graph.add_conditional_edges(
            "validate_step",
            self._create_logged_router("post_validation_router", post_validation_router),
            {
                "run_workflow_step": "run_workflow_step",
                "workflow_end": "workflow_end",
                "handle_error": "handle_error"
            }
        )

        genome_graph.add_conditional_edges(
            "run_workflow_step",
            self._create_logged_router("next_step_router", next_step_router),
            {
                "validate_step": "validate_step",
                "workflow_end": "workflow_end",
                "handle_error": "handle_error"
            }
        )

        genome_graph.add_edge("handle_error", END)
        genome_graph.add_edge("workflow_end", END)
        genome_graph.set_entry_point("validate_step")

        return genome_graph.compile()
    
    def run(self, state):
        """Run execution workflow with logging."""
        workflow_logger.info(f"STARTING EXECUTION WORKFLOW")
        workflow_logger.info(f"Initial Steps: {len(state.get('steps_to_run', []))}")
        workflow_logger.info(f"Narrative ID: {state.get('narrative_id')}")
        
        final_state = self.graph.invoke(state)
        
        workflow_logger.info(f"EXECUTION WORKFLOW COMPLETED")
        workflow_logger.info(f"Final Steps: {len(final_state.get('steps_to_run', []))}")
        workflow_logger.info(f"Final Error: {final_state.get('error')}")
        workflow_logger.info(f"Final Results: {final_state.get('results')}")
        
        return final_state