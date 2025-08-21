from io import StringIO
import json
import os
import uuid
from ansi2html import Ansi2HTMLConverter
import dash_bootstrap_components as dbc
from dash_extensions import Purify
from dash import MATCH, dcc, callback_context, html, Input, Output, callback, State

from narrative_llm_agent.user_interface.streaming import StreamRedirector
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE, SESSION_ID_STORE, WORKFLOW_INSTANCES, WORKFLOW_STORE
from narrative_llm_agent.util.json_util import make_json_serializable
from narrative_llm_agent.workflow_graph.graph_hitl import (
    ExecutionWorkflow,
)

APP_LOG_BUFFERS = {}

def create_approval_interface(workflow_state: dict, session_id):
    """Create the approval interface for the analysis plan"""
    if not workflow_state:
        return html.Div("No workflow state available")

    steps = workflow_state.get("steps_to_run", [])
    if not steps:
        return html.Div("No steps found in workflow state")

    APP_LOG_BUFFERS[session_id] = StringIO()

    # Create table data
    table_data = []
    for step in steps:
        table_data.append({
            "Step": step.get("Step", "Unknown"),
            "Name": step.get("Name", "Unnamed Step"),
            "App": step.get("App", "Unknown App"),
            "App ID": step.get("app_id", "Unknown ID"),
            "Description": step.get("Description", "No description"),
            "Creates Object": "Yes" if step.get("expect_new_object", False) else "No",
        })

    # Create table rows
    table_rows = []
    for row in table_data:
        table_rows.append(
            html.Tr([
                html.Td(row["Step"], className="text-center fw-bold"),
                html.Td(row["Name"], className="fw-semibold"),
                html.Td(row["App"]),
                html.Td(html.Code(row["App ID"], className="text-primary")),
                html.Td(row["Description"], style={"maxWidth": "300px"}),
                html.Td(
                    dbc.Badge(
                        row["Creates Object"],
                        color="success" if row["Creates Object"] == "Yes" else "secondary",
                        className="me-1",
                    ),
                    className="text-center",
                ),
            ])
        )

    analysis_table = html.Table(
        [
            html.Thead([
                html.Tr([
                    html.Th("Step", className="text-center"),
                    html.Th("Name"),
                    html.Th("KBase App"),
                    html.Th("App ID"),
                    html.Th("Description"),
                    html.Th("Creates Object", className="text-center"),
                ], className="table-dark")
            ]),
            html.Tbody(table_rows),
        ],
        className="table table-striped table-hover",
    )

    layout = dbc.Card(
        [
            dbc.CardHeader([
                html.H4([
                    html.I(className="bi bi-clipboard-check me-2"),
                    "Analysis Plan - Awaiting Approval",
                ], className="mb-0")
            ]),
            dbc.CardBody([
                dbc.Alert([
                    html.I(className="bi bi-info-circle me-2"),
                    f"Found {len(steps)} analysis steps ready for execution. Please review and approve the plan below.",
                ], color="info", className="mb-3"),
                html.H5("📋 Proposed Analysis Steps:", className="mb-3"),
                html.Div(analysis_table, className="table-responsive", style={"maxHeight": "500px", "overflowY": "auto"}),
                html.Hr(),
                dbc.Row([
                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button([
                                html.I(className="bi bi-check-circle me-2"),
                                "Approve Plan",
                            ], id="approve-btn", color="success", size="lg"),
                            dbc.Button([
                                html.I(className="bi bi-x-circle me-2"),
                                "Reject Plan",
                            ], id="reject-btn", color="danger", size="lg"),
                            dbc.Button([
                                html.I(className="bi bi-stop-circle me-2"),
                                "Cancel",
                            ], id="cancel-btn", color="secondary", size="lg"),
                        ])
                    ], width=12, className="text-center")
                ], className="mb-3"),
                html.Div(
                    id="feedback-area",
                    style={"display": "none"},
                    children=[
                        html.Hr(),
                        dbc.Label("💬 Feedback (optional):"),
                        dbc.Textarea(
                            id="feedback-text",
                            placeholder="Provide feedback for plan modifications...",
                            rows=3,
                            className="mb-2",
                        ),
                        dbc.Button([
                            html.I(className="bi bi-send me-2"),
                            "Submit Feedback",
                        ], id="submit-feedback-btn", color="warning"),
                    ],
                ),
                html.Div(id="approval-status", className="mt-3"),
                html.Div(
                    [
                        dcc.Interval(id="app-log-poller", interval=1000, disabled=True),
                        dcc.Store(id="app-scroll-trigger"),
                        html.Div(
                            id="app-log-output",
                            style={
                                "whiteSpace": "pre-wrap",
                                "height": "500px",
                                "overflowY": "auto",
                                "fontFamily": "monospace",
                                "border": "1px solid #dee2e6",
                                "padding": "0.375rem 0.75rem",
                                "fontSize": "1rem",
                                "borderRadius": "0.375rem",

                            },
                        ),
                    ],
                    id="app-log-container",
                    style={"display": "none"}
                )
            ]),
        ],
        className="shadow-sm",
    )
    return layout

@callback(
    [
        Output("execution-state-store", "data"),
        Output("approval-status", "children")
    ],
    [
        Input("approve-btn", "n_clicks"),
        Input("reject-btn", "n_clicks"),
        Input("cancel-btn", "n_clicks"),
    ],
    [
        State(WORKFLOW_STORE, "data"),
        State(CREDENTIALS_STORE, "data"),
        State(SESSION_ID_STORE, "data")
    ],
    prevent_initial_call=True,
)
def handle_approval(approve_clicks, reject_clicks, cancel_clicks, workflow_state, credentials, session_id):
    ctx = callback_context
    if not ctx.triggered:
        return {}, html.Div()

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "approve-btn" and approve_clicks:
        if session_id not in APP_LOG_BUFFERS:
            return {}, "missing app log buffer!?"

        loading_status = dbc.Alert("🔄 Executing approved workflow... Please wait.", color="info")

        try:
            # Get the nested workflow state and update it properly
            inner_workflow_state = workflow_state.get("workflow_state", {})
            inner_workflow_state["human_approval_status"] = "approved"
            inner_workflow_state["awaiting_approval"] = False
            inner_workflow_state["input_object_upa"] = workflow_state.get("reads_id")

            # Execute the workflow
            with StreamRedirector(APP_LOG_BUFFERS[session_id]):
                try:
                    execution_result = run_analysis_execution(
                        workflow_state.get("workflow_state", {}),
                        credentials,
                        workflow_state.get("workflow_key"),
                    )
                finally:
                    del APP_LOG_BUFFERS[session_id]

            # Update execution state
            execution_state = {
                "status": execution_result.get("status", "unknown"),
                "final_state": execution_result.get("final_state", {}),
                "error": execution_result.get("error"),
            }

            if execution_result.get("status") == "completed":
                success_status = dbc.Alert("✅ Workflow approved and executed successfully!", color="success")
                return execution_state, success_status
            else:
                error_status = dbc.Alert(
                    f"❌ Execution failed: {execution_result.get('error', 'Unknown error')}",
                    color="danger",
                )
                return execution_state, error_status

        except Exception as e:
            print("an error occurred")
            print(e)
            error_state = {"status": "error", "error": str(e)}
            error_status = dbc.Alert(f"❌ Error during execution: {str(e)}", color="danger")
            return error_state, error_status

    elif button_id == "reject-btn" and reject_clicks:
        feedback_status = html.Div([
            dbc.Alert("❌ Plan rejected. Please provide feedback below.", color="warning"),
            html.Script("document.getElementById('feedback-area').style.display = 'block';"),
        ])
        return {"status": "rejected"}, feedback_status

    elif button_id == "cancel-btn" and cancel_clicks:
        cancel_status = dbc.Alert("🚫 Workflow cancelled.", color="secondary")
        return {"status": "cancelled"}, cancel_status

    return {}, html.Div()

@callback(
    [
        Output("app-log-poller", "disabled"),
        Output("app-log-container", "style"),
    ],
    [
        Input("approve-btn", "n_clicks")
    ],
    prevent_initial_call=True,
)
def start_app_poller(n_clicks):
    return (False if n_clicks else True), {}

@callback(
    [
        Output("app-log-output", "children"),
        Output("app-scroll-trigger", "data"),
    ],
    [
        Input("app-log-poller", "n_intervals"),
    ],
    [
        State(SESSION_ID_STORE, "data")
    ],
    prevent_initial_call=True,
)
def update_app_log(_, session_id):
    if session_id in APP_LOG_BUFFERS:
        log_value = APP_LOG_BUFFERS[session_id].getvalue()
        html_value = Ansi2HTMLConverter(inline=True).convert(log_value, full=False)
        return Purify(html=(f"<div>{html_value}</div>")), {"scroll": True}


def run_analysis_execution(workflow_state, credentials, workflow_key=None):
    """Run the analysis execution phase after approval"""
    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            used_llm = "gpt-4.1-cborg"
            api_key = credentials.get("cborg_api_key")
        else:
            used_llm = "gpt-4o-openai"
            api_key = credentials.get("openai_api_key")

        # Set Neo4j environment variables if they exist
        neo4j_uri = credentials.get("neo4j_uri", os.environ.get("NEO4J_URI", ""))
        neo4j_username = credentials.get("neo4j_username", os.environ.get("NEO4J_USERNAME", ""))
        neo4j_password = credentials.get("neo4j_password", os.environ.get("NEO4J_PASSWORD", ""))

        if neo4j_uri:
            os.environ["NEO4J_URI"] = neo4j_uri
        if neo4j_username:
            os.environ["NEO4J_USERNAME"] = neo4j_username
        if neo4j_password:
            os.environ["NEO4J_PASSWORD"] = neo4j_password

        # Load the KBase classes
        # success, result = load_kbase_classes()
        # if not success:
        #     return {"error": result, "status": "error"}

        # ExecutionWorkflow = result["ExecutionWorkflow"]

        # Create execution workflow instance
        execution_workflow = ExecutionWorkflow(
            analyst_llm=used_llm,
            analyst_token=api_key,
            validator_llm=used_llm,
            validator_token=api_key,
            app_flow_llm=used_llm,
            app_flow_token=api_key,
            writer_llm=used_llm,
            writer_token=api_key,
            kbase_token=kb_auth_token,
        )

        # Run the execution phase
        final_state = execution_workflow.run(workflow_state)

        # Make the final_state JSON serializable
        final_state_serializable = make_json_serializable(final_state)
        print("=== FINAL STATE ===")
        print(json.dumps(final_state, indent=2, default=str))

        # Clean up stored workflow instance if provided
        if workflow_key and workflow_key in WORKFLOW_INSTANCES:
            del WORKFLOW_INSTANCES[workflow_key]

        return {
            "final_state": final_state_serializable,
            "error": final_state_serializable.get("error"),
            "status": "completed" if final_state_serializable.get("results") else "error",
        }

    except Exception as e:
        print(f"an error occurred: {e}")
        return {"error": str(e), "status": "error"}


