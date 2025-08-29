from io import StringIO
from ansi2html import Ansi2HTMLConverter
import dash_bootstrap_components as dbc
from dash_extensions import Purify
from dash import dcc, callback_context, html, Input, Output, callback, State
import os

from narrative_llm_agent.user_interface.streaming import StreamRedirector
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE, SESSION_ID_STORE, WORKFLOW_STORE
from narrative_llm_agent.user_interface.workflow_runners import run_analysis_execution
from narrative_llm_agent.user_interface.components.redis_streaming import RedisStreamRedirector, redis_client, get_logs_from_redis

from narrative_llm_agent.user_interface.components.redis_streaming import get_background_callback_manager, get_redis_client

#setup callback manager and redis client for long callbacks using redis or diskcache

celery_app = None
if 'REDIS_URL' in os.environ:
    from celery import Celery
    celery_app = Celery(__name__, broker=os.environ['REDIS_URL'], backend=os.environ['REDIS_URL'])

background_callback_manager = get_background_callback_manager(celery_app)
redis_client = get_redis_client()

APP_LOG_BUFFERS = {}

def create_approval_interface(workflow_state: dict, session_id):
    """Create the approval interface for the analysis plan"""
    if not workflow_state:
        return html.Div("No workflow state available")

    steps = workflow_state.get("steps_to_run", [])
    if not steps:
        return html.Div("No steps found in workflow state")

    if not redis_client:
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
    background=True,
    manager=background_callback_manager
)
def handle_approval(approve_clicks, reject_clicks, cancel_clicks, workflow_state, credentials, session_id):
    ctx = callback_context
    if not ctx.triggered:
        return {}, html.Div()

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "approve-btn" and approve_clicks:
        if not redis_client and session_id not in APP_LOG_BUFFERS:
            return {}, "missing app log buffer!?"

        loading_status = dbc.Alert("🔄 Executing approved workflow... Please wait.", color="info")

        try:
            # Get the nested workflow state and update it properly
            inner_workflow_state = workflow_state.get("workflow_state", {})
            inner_workflow_state["human_approval_status"] = "approved"
            inner_workflow_state["awaiting_approval"] = False
            inner_workflow_state["input_object_upa"] = workflow_state.get("reads_id")

            # Setup streaming based on environment
            if redis_client:
                # Redis-based streaming for production
                stream_redirector = RedisStreamRedirector(session_id, redis_client, "execution")
                
                # Log initial message to Redis
                stream_redirector.write("Starting KBase workflow execution...\n")
                stream_redirector.write(f"Session ID: {session_id}\n")
                stream_redirector.write("=" * 50 + "\n")
                
            else:
                # Local buffer for development
                stream_redirector = StreamRedirector(APP_LOG_BUFFERS[session_id])
                
                print("Starting KBase workflow execution")
                print(f"Session ID: {session_id}")
                print("=" * 50)

            try:
                # Redirect stdout to our streaming mechanism
                import sys
                original_stdout = sys.stdout
                sys.stdout = stream_redirector
                
                try:
                    execution_result = run_analysis_execution(
                        workflow_state.get("workflow_state", {}),
                        credentials,
                        workflow_state.get("workflow_key"),
                    )
                finally:
                    sys.stdout = original_stdout
                    
                # Log completion
                if redis_client:
                    stream_redirector.write(f"\nWorkflow execution completed with status: {execution_result.get('status', 'unknown')}\n")
                else:
                    print(f"\nWorkflow execution completed with status: {execution_result.get('status', 'unknown')}")
                    
            except Exception as e:
                # Restore stdout
                import sys
                sys.stdout = original_stdout
                
                error_msg = f"Error during workflow execution: {str(e)}"
                if redis_client:
                    stream_redirector.write(error_msg + "\n")
                else:
                    print(error_msg)
                    
                execution_result = {"status": "error", "error": str(e)}
            finally:
                if not redis_client and session_id in APP_LOG_BUFFERS:
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
    background=True,
    manager=background_callback_manager
)
def update_app_log(n_intervals, session_id):
    if not session_id:
        return html.Div(), {}
    
    log_content = ""
    
    if redis_client:
        # Redis-based logging
        log_content = get_logs_from_redis(session_id, "execution")
    else:
        # Local buffer-based logging
        if session_id in APP_LOG_BUFFERS:
            log_content = APP_LOG_BUFFERS[session_id].getvalue()
    
    if log_content:
        html_content = Ansi2HTMLConverter(inline=True).convert(log_content, full=False)
        return Purify(html=f"<div style='white-space: pre-wrap;'>{html_content}</div>"), {"scroll": True}
    
    return html.Div("Waiting for execution to start..."), {}