import time
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
import json
import os
from datetime import datetime

from narrative_llm_agent.user_interface.components.analysis_setup import create_analysis_input_form
from narrative_llm_agent.user_interface.components.credentials import create_credentials_form
from narrative_llm_agent.util.json_util import make_json_serializable

# Initialize the Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "KBase Research Agent"

# Global variable for workflow management
analysis_history = []

CREDENTIALS_STORE = "credentials-store"
WORKFLOW_STORE = "workflow-state-store"

# KBase Integration Classes
def load_kbase_classes():
    """Load and cache KBase classes"""
    try:
        from narrative_llm_agent.workflow_graph.graph_hitl import (
            AnalysisWorkflow,
            ExecutionWorkflow,
        )
        from narrative_llm_agent.writer_graph.mra_graph import MraWriterGraph
        from narrative_llm_agent.writer_graph.summary_graph import SummaryWriterGraph
        from narrative_llm_agent.kbase.clients.workspace import Workspace
        from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine

        return True, {
            "AnalysisWorkflow": AnalysisWorkflow,
            "ExecutionWorkflow": ExecutionWorkflow,
            "MraWriterGraph": MraWriterGraph,
            "SummaryWriterGraph": SummaryWriterGraph,
            "Workspace": Workspace,
            "ExecutionEngine": ExecutionEngine,
        }
    except ImportError as e:
        return False, f"ImportError: {str(e)}"
    except Exception as e:
        return False, f"Error loading KBase classes: {str(e)}"


workflow_instances = {}

def set_environment_credentials(credentials: dict[str, str]) -> str:
    """
    TODO (critical!): these should not be set as environment vars.
    In a multi-user app, these will bleed into multiple user sessions.

    Ok for now for prototyping, but user-set creds should be passed around
    to the various LLMs.

    returns the kb_auth_token as a str
    """
    # Get credentials and set environment variables
    kb_auth_token = credentials.get("kb_auth_token", "")
    provider = credentials.get("provider", "openai")

    if provider == "cborg":
        api_key = credentials.get(
            "cborg_api_key", os.environ.get("CBORG_API_KEY", "")
        )
    else:
        api_key = credentials.get(
            "openai_api_key", os.environ.get("OPENAI_API_KEY", "")
        )

    # Set environment variables
    # TODO: these should just be passed around, not used as env vars:
    # the environment will be the same for a multi-user system
    os.environ["KB_AUTH_TOKEN"] = kb_auth_token
    if provider == "cborg":
        os.environ["CBORG_API_KEY"] = api_key
    else:
        os.environ["OPENAI_API_KEY"] = api_key

    # Set Neo4j environment variables if they exist
    neo4j_uri = credentials.get("neo4j_uri", os.environ.get("NEO4J_URI", ""))
    neo4j_username = credentials.get(
        "neo4j_username", os.environ.get("NEO4J_USERNAME", "")
    )
    neo4j_password = credentials.get(
        "neo4j_password", os.environ.get("NEO4J_PASSWORD", "")
    )

    if neo4j_uri:
        os.environ["NEO4J_URI"] = neo4j_uri
    if neo4j_username:
        os.environ["NEO4J_USERNAME"] = neo4j_username
    if neo4j_password:
        os.environ["NEO4J_PASSWORD"] = neo4j_password

    return kb_auth_token


def analysis_plan_simple_test(narrative_id: int, reads_id: str, description: str, credentials: dict[str, str]) -> dict:
    print("starting analysis planner.")
    for i in range(10):
        time.sleep(5)
        print("still planning...")
    print("done!")
    return {
        "narrative_id": narrative_id,
        "reads_id": reads_id,
        "description": description,
        "workflow_state": {},
        "workflow_key": "foo",  # Reference to stored instance
        "error": None,
        "status": "awaiting_approval"
    }


def run_analysis_planning(narrative_id, reads_id, description, credentials):
    """Run the analysis planning phase only"""
    try:
        print("setting credentials")
        kb_auth_token = set_environment_credentials(credentials)

        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            print(f"Error loading KBase classes: {result}")
            return {
                "narrative_id": narrative_id,
                "reads_id": reads_id,
                "description": description,
                "workflow_state": None,
                "error": result,
                "status": "error",
            }

        AnalysisWorkflow = result["AnalysisWorkflow"]

        # Create workflow instance
        workflow = AnalysisWorkflow(
            analyst_llm="gpt-4.1-cborg",
            app_flow_llm="gpt-4.1-cborg",
            token=kb_auth_token,
        )

        # Run the planning phase only
        workflow_state = workflow.run(
            narrative_id=narrative_id, reads_id=reads_id, description=description
        )

        # Store workflow instance globally (not in the returned dict)
        workflow_key = f"{narrative_id}_{reads_id}"
        workflow_instances[workflow_key] = workflow

        # Return JSON-serializable data only
        result = {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": workflow_state,
            "workflow_key": workflow_key,  # Reference to stored instance
            "error": workflow_state.get("error"),
            "status": "awaiting_approval"
            if workflow_state.get("awaiting_approval")
            else "completed",
        }

    except Exception as e:
        result = {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": None,
            "error": str(e),
            "status": "error",
        }

    # Update analysis history
    global analysis_history
    analysis_history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "status": result.get("status", "unknown"),
            "error": result.get("error"),
        }
    )

    return result



def run_analysis_execution(workflow_state, credentials, workflow_key=None):
    """Run the analysis execution phase after approval"""
    try:
        kb_auth_token = set_environment_credentials(credentials)

        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {"error": result, "status": "error"}

        ExecutionWorkflow = result["ExecutionWorkflow"]

        # Create execution workflow instance
        execution_workflow = ExecutionWorkflow(
            analyst_llm="gpt-4.1-cborg",
            validator_llm="gpt-4.1-cborg",
            app_flow_llm="gpt-4.1-cborg",
            writer_llm="gpt-4.1-cborg",
            token=kb_auth_token,
        )

        # Run the execution phase
        final_state = execution_workflow.run(workflow_state)

        # Make the final_state JSON serializable
        final_state_serializable = make_json_serializable(final_state)
        print("=== FINAL STATE ===")
        print(json.dumps(final_state, indent=2, default=str))
        # Clean up stored workflow instance if provided
        if workflow_key and workflow_key in workflow_instances:
            del workflow_instances[workflow_key]

        return {
            "final_state": final_state_serializable,
            "error": final_state_serializable.get("error"),
            "status": "completed"
            if final_state_serializable.get("results")
            else "error",
        }

    except Exception as e:
        return {"error": str(e), "status": "error"}


# MRA Generation function (keep existing)
def generate_mra_draft(narrative_id, credentials):
    """Generate MRA draft using the MraWriterGraph"""
    try:
        # Load the KBase classes
        success, result = load_kbase_classes()
        if not success:
            return {"mra_draft": None, "error": result}

        MraWriterGraph = result["MraWriterGraph"]
        Workspace = result["Workspace"]
        ExecutionEngine = result["ExecutionEngine"]

        # Create KBase clients
        ws_client = Workspace()
        ee_client = ExecutionEngine()

        # Create MRA writer
        mra_writer = MraWriterGraph(ws_client, ee_client)

        # Run the MRA workflow
        mra_writer.run_workflow(narrative_id)

        return {
            "mra_draft": "The MRA draft has been successfully generated.",
            "error": None,
        }

    except Exception as e:
        return {"mra_draft": None, "error": str(e)}





# And update your main layout to use Dash's loading component:

# app.layout = dbc.Container(
#     [
#         dcc.Store(id="credentials-store"),
#         dcc.Store(id="workflow-state-store"),
#         dcc.Store(id="execution-state-store"),
#         dcc.Store(id="analysis-history-store", data=[]),
#         # Header
#         dbc.Row(
#             [
#                 dbc.Col(
#                     [
#                         html.H1("🧬 KBase Research Agent", className="display-4 mb-4"),
#                         html.P(
#                             "Automated genome analysis workflows with human approval",
#                             className="lead",
#                         ),
#                     ]
#                 )
#             ],
#             className="mb-4",
#         ),
#         # Main content
#         html.Div(
#             id="main-content",
#             children=[
#                 create_credentials_form("credentials-store"),
#                 html.Br(),
#                 create_input_form(),
#                 html.Br(),
#                 # Use Dash's built-in loading component instead of manual loading div
#                 dcc.Loading(
#                     id="loading-analysis",
#                     type="default",
#                     children=html.Div(id="analysis-results"),
#                 ),
#             ],
#         ),
#     ],
#     fluid=True,
# )


def create_approval_interface(workflow_state):
    """Create the approval interface for the analysis plan"""
    print("inside approval interface", workflow_state.get("steps_to_run"))
    if not workflow_state or not workflow_state.get("steps_to_run"):
        return html.Div()

    # Format the steps for display
    steps = workflow_state.get("steps_to_run", [])

    # Create table data - the steps already have the correct structure
    table_data = []
    for step in steps:
        table_data.append(
            {
                "Step": step.get("Step", "Unknown"),
                "Name": step.get("Name", "Unnamed Step"),
                "App": step.get("App", "Unknown App"),
                "App ID": step.get("app_id", "Unknown ID"),
                "Description": step.get("Description", "No description"),
                "Creates Object": "Yes"
                if step.get("expect_new_object", False)
                else "No",
            }
        )

    return dbc.Card(
        [
            dbc.CardHeader("📋 Analysis Plan - Awaiting Approval"),
            dbc.CardBody(
                [
                    html.H5("Proposed Analysis Steps:", className="mb-3"),
                    # Steps table
                    dash_table.DataTable(
                        data=table_data,
                        columns=[
                            {"name": "Step", "id": "Step", "type": "numeric"},
                            {"name": "Name", "id": "Name"},
                            {"name": "App", "id": "App"},
                            {"name": "App ID", "id": "App ID"},
                            {"name": "Description", "id": "Description"},
                            {"name": "Creates Object", "id": "Creates Object"},
                        ],
                        style_cell={
                            "textAlign": "left",
                            "padding": "10px",
                            "whiteSpace": "normal",
                            "height": "auto",
                            "minWidth": "100px",
                            "maxWidth": "300px",
                        },
                        style_header={
                            "backgroundColor": "rgb(230, 230, 230)",
                            "fontWeight": "bold",
                        },
                        style_data_conditional=[
                            {
                                "if": {"row_index": "odd"},
                                "backgroundColor": "rgb(248, 248, 248)",
                            }
                        ],
                        style_table={"overflowX": "auto"},
                    ),
                    html.Hr(),
                    # Approval buttons
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Button(
                                        "✅ Approve Plan",
                                        id="approve-btn",
                                        color="success",
                                        size="lg",
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        "❌ Reject Plan",
                                        id="reject-btn",
                                        color="danger",
                                        size="lg",
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        "🚫 Cancel",
                                        id="cancel-btn",
                                        color="secondary",
                                        size="lg",
                                    ),
                                ],
                                width=12,
                            )
                        ],
                        className="mb-3",
                    ),
                    # Feedback area (initially hidden)
                    html.Div(
                        id="feedback-area",
                        style={"display": "none"},
                        children=[
                            html.Hr(),
                            dbc.Label("Feedback (optional):"),
                            dbc.Textarea(
                                id="feedback-text",
                                placeholder="Provide feedback for plan modifications...",
                                rows=3,
                            ),
                            dbc.Button(
                                "Submit Feedback",
                                id="submit-feedback-btn",
                                color="warning",
                                className="mt-2",
                            ),
                        ],
                    ),
                    html.Div(id="approval-status", className="mt-3"),
                ]
            ),
        ]
    )


def create_execution_display(execution_result):
    """Create display for execution results"""
    if not execution_result:
        return html.Div()

    components = []

    if execution_result.get("status") == "running":
        components.append(
            dbc.Alert(
                "🔄 Executing analysis workflow... This may take several minutes.",
                color="info",
            )
        )
    elif execution_result.get("status") == "completed":
        components.append(
            dbc.Alert("✅ Analysis workflow completed successfully!", color="success")
        )

        # Show final results
        final_state = execution_result.get("final_state", {})
        if final_state.get("results"):
            components.append(
                dbc.Card(
                    [
                        dbc.CardHeader("🧪 Workflow Results"),
                        dbc.CardBody([html.Pre(str(final_state["results"]))]),
                    ],
                    className="mb-3",
                )
            )

        # MRA Generation Button
        components.append(
            dbc.Card(
                [
                    dbc.CardHeader("📄 Generate MRA Draft"),
                    dbc.CardBody(
                        [
                            html.P(
                                "Analysis completed successfully! You can now generate a Microbiology Resource Announcements (MRA) draft paper."
                            ),
                            dbc.Button(
                                "📝 Generate MRA Draft",
                                id="generate-mra-btn",
                                color="primary",
                                size="lg",
                            ),
                            html.Div(id="mra-results", className="mt-3"),
                        ]
                    ),
                ],
                className="mb-3",
            )
        )

    elif execution_result.get("status") == "error":
        components.append(
            dbc.Alert(
                f"❌ Error: {execution_result.get('error', 'Unknown error')}",
                color="danger",
            )
        )

    return html.Div(components)


# Add this callback to display execution results
@app.callback(
    Output("analysis-results", "children", allow_duplicate=True),
    Input("execution-state-store", "data"),
    State("analysis-results", "children"),
    prevent_initial_call=True,
)
def display_execution_results(execution_state, current_results):
    if not execution_state:
        return current_results

    # Print execution state to console for debugging
    print("=== EXECUTION STATE UPDATE ===")
    print(f"Status: {execution_state}")
    if execution_state.get("final_state"):
        print("Final State:")
        print(json.dumps(execution_state.get("final_state"), indent=2, default=str))
    print("=" * 35)

    # Create execution display
    execution_display = create_execution_display(execution_state)

    return execution_display


# def create_approval_interface(workflow_state):
#     """Create the approval interface for the analysis plan"""
#     print("inside approval interface", workflow_state.get("steps_to_run"))
#     if not workflow_state:
#         return html.Div("No workflow state available")

#     steps = workflow_state.get("steps_to_run", [])
#     if not steps:
#         return html.Div("No steps found in workflow state")

#     # Create table data
#     table_data = []
#     for step in steps:
#         table_data.append(
#             {
#                 "Step": step.get("Step", "Unknown"),
#                 "Name": step.get("Name", "Unnamed Step"),
#                 "App": step.get("App", "Unknown App"),
#                 "App ID": step.get("app_id", "Unknown ID"),
#                 "Description": step.get("Description", "No description"),
#                 "Creates Object": "Yes"
#                 if step.get("expect_new_object", False)
#                 else "No",
#             }
#         )

#     # Create a styled Bootstrap table
#     table_rows = []
#     for row in table_data:
#         table_rows.append(
#             html.Tr(
#                 [
#                     html.Td(row["Step"], className="text-center fw-bold"),
#                     html.Td(row["Name"], className="fw-semibold"),
#                     html.Td(row["App"]),
#                     html.Td(html.Code(row["App ID"], className="text-primary")),
#                     html.Td(row["Description"], style={"max-width": "300px"}),
#                     html.Td(
#                         dbc.Badge(
#                             row["Creates Object"],
#                             color="success"
#                             if row["Creates Object"] == "Yes"
#                             else "secondary",
#                             className="me-1",
#                         ),
#                         className="text-center",
#                     ),
#                 ]
#             )
#         )

#     analysis_table = html.Table(
#         [
#             html.Thead(
#                 [
#                     html.Tr(
#                         [
#                             html.Th("Step", className="text-center"),
#                             html.Th("Name"),
#                             html.Th("KBase App"),
#                             html.Th("App ID"),
#                             html.Th("Description"),
#                             html.Th("Creates Object", className="text-center"),
#                         ],
#                         className="table-dark",
#                     )
#                 ]
#             ),
#             html.Tbody(table_rows),
#         ],
#         className="table table-striped table-hover",
#     )

#     return dbc.Card(
#         [
#             dbc.CardHeader(
#                 [
#                     html.H4(
#                         [
#                             html.I(className="bi bi-clipboard-check me-2"),
#                             "Analysis Plan - Awaiting Approval",
#                         ],
#                         className="mb-0",
#                     )
#                 ]
#             ),
#             dbc.CardBody(
#                 [
#                     dbc.Alert(
#                         [
#                             html.I(className="bi bi-info-circle me-2"),
#                             f"Found {len(steps)} analysis steps ready for execution. Please review and approve the plan below.",
#                         ],
#                         color="info",
#                         className="mb-3",
#                     ),
#                     html.H5("📋 Proposed Analysis Steps:", className="mb-3"),
#                     # Scrollable table container
#                     html.Div(
#                         analysis_table,
#                         className="table-responsive",
#                         style={"max-height": "500px", "overflow-y": "auto"},
#                     ),
#                     html.Hr(),
#                     # Approval buttons
#                     dbc.Row(
#                         [
#                             dbc.Col(
#                                 [
#                                     dbc.ButtonGroup(
#                                         [
#                                             dbc.Button(
#                                                 [
#                                                     html.I(
#                                                         className="bi bi-check-circle me-2"
#                                                     ),
#                                                     "Approve Plan",
#                                                 ],
#                                                 id="approve-btn",
#                                                 color="success",
#                                                 size="lg",
#                                             ),
#                                             dbc.Button(
#                                                 [
#                                                     html.I(
#                                                         className="bi bi-x-circle me-2"
#                                                     ),
#                                                     "Reject Plan",
#                                                 ],
#                                                 id="reject-btn",
#                                                 color="danger",
#                                                 size="lg",
#                                             ),
#                                             dbc.Button(
#                                                 [
#                                                     html.I(
#                                                         className="bi bi-stop-circle me-2"
#                                                     ),
#                                                     "Cancel",
#                                                 ],
#                                                 id="cancel-btn",
#                                                 color="secondary",
#                                                 size="lg",
#                                             ),
#                                         ]
#                                     )
#                                 ],
#                                 width=12,
#                                 className="text-center",
#                             )
#                         ],
#                         className="mb-3",
#                     ),
#                     # Feedback area (initially hidden)
#                     html.Div(
#                         id="feedback-area",
#                         style={"display": "none"},
#                         children=[
#                             html.Hr(),
#                             dbc.Label("💬 Feedback (optional):"),
#                             dbc.Textarea(
#                                 id="feedback-text",
#                                 placeholder="Provide feedback for plan modifications...",
#                                 rows=3,
#                                 className="mb-2",
#                             ),
#                             dbc.Button(
#                                 [
#                                     html.I(className="bi bi-send me-2"),
#                                     "Submit Feedback",
#                                 ],
#                                 id="submit-feedback-btn",
#                                 color="warning",
#                             ),
#                         ],
#                     ),
#                     html.Div(id="approval-status", className="mt-3"),
#                 ]
#             ),
#         ],
#         className="shadow-sm",
#     )


# Add this callback to handle approval actions
@app.callback(
    [Output("execution-state-store", "data"), Output("approval-status", "children")],
    [
        Input("approve-btn", "n_clicks"),
        Input("reject-btn", "n_clicks"),
        Input("cancel-btn", "n_clicks"),
    ],
    [State(WORKFLOW_STORE, "data"), State(CREDENTIALS_STORE, "data")],
    prevent_initial_call=True,
)
def handle_approval(
    approve_clicks, reject_clicks, cancel_clicks, workflow_state, credentials
):
    ctx = callback_context
    if not ctx.triggered:
        return {}, html.Div()

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "approve-btn" and approve_clicks:
        # Show loading status
        loading_status = dbc.Alert(
            "🔄 Executing approved workflow... Please wait.", color="info"
        )

        try:
            # Print the current workflow state for debugging
            print("=== WORKFLOW STATE BEFORE EXECUTION ===")
            print(json.dumps(workflow_state, indent=2, default=str))
            print("=" * 50)
            # Get the nested workflow state and update it properly
            inner_workflow_state = workflow_state.get("workflow_state", {})

            # Update the approval status in the inner workflow state
            inner_workflow_state["human_approval_status"] = "approved"
            inner_workflow_state["awaiting_approval"] = False
            inner_workflow_state["input_object_upa"] = workflow_state.get("reads_id")

            print("=== UPDATED WORKFLOW STATE ===")
            print(json.dumps(inner_workflow_state, indent=2, default=str))
            print("=" * 35)
            # # Execute the workflow
            execution_result = run_analysis_execution(
                workflow_state.get("workflow_state", {}),
                credentials,
                workflow_state.get("workflow_key"),
            )

            # # Print the execution result
            print("=== EXECUTION RESULT ===")
            print(json.dumps(execution_result, indent=2, default=str))
            print("=" * 30)

            # # Update execution state
            execution_state = {
                "status": execution_result.get("status", "unknown"),
                "final_state": execution_result.get("final_state", {}),
                "error": execution_result.get("error"),
            }

            if execution_result.get("status") == "completed":
                success_status = dbc.Alert(
                    "✅ Workflow approved and executed successfully!", color="success"
                )
                return execution_state, success_status
            else:
                error_status = dbc.Alert(
                    f"❌ Execution failed: {execution_result.get('error', 'Unknown error')}",
                    color="danger",
                )
                return execution_state, error_status

        except Exception as e:
            print(f"Exception during execution: {str(e)}")
            error_state = {"status": "error", "error": str(e)}
            error_status = dbc.Alert(
                f"❌ Error during execution: {str(e)}", color="danger"
            )
            return error_state, error_status

    elif button_id == "reject-btn" and reject_clicks:
        # Show feedback area
        feedback_status = html.Div(
            [
                dbc.Alert(
                    "❌ Plan rejected. Please provide feedback below.", color="warning"
                ),
                html.Script(
                    "document.getElementById('feedback-area').style.display = 'block';"
                ),
            ]
        )
        return {"status": "rejected"}, feedback_status

    elif button_id == "cancel-btn" and cancel_clicks:
        cancel_status = dbc.Alert("🚫 Workflow cancelled.", color="secondary")
        return {"status": "cancelled"}, cancel_status

    return {}, html.Div()


# Also add a callback to handle feedback submission
@app.callback(
    Output("approval-status", "children", allow_duplicate=True),
    Input("submit-feedback-btn", "n_clicks"),
    State("feedback-text", "value"),
    prevent_initial_call=True,
)
def handle_feedback_submission(n_clicks, feedback_text):
    if n_clicks:
        # Print feedback for debugging
        print("=== USER FEEDBACK ===")
        print(f"Feedback: {feedback_text}")
        print("=" * 25)

        return dbc.Alert(
            [
                html.I(className="bi bi-chat-dots me-2"),
                "Thank you for your feedback. Please modify the analysis parameters and try again.",
            ],
            color="info",
        )

    return html.Div()


# Callback for MRA generation
@app.callback(
    Output("mra-results", "children"),
    Input("generate-mra-btn", "n_clicks"),
    [State(CREDENTIALS_STORE, "data"), State("narrative-id", "value")],
    prevent_initial_call=True,
)
def generate_mra(n_clicks, credentials, narrative_id):
    # Check if button was actually clicked
    if not n_clicks or n_clicks == 0:
        return html.Div()
    if n_clicks and credentials and credentials.get("kb_auth_token"):
        # Show loading message first
        loading_alert = dbc.Alert(
            "🔄 Generating MRA draft... This may take a few minutes.", color="info"
        )

        try:
            # Generate MRA draft
            mra_result = generate_mra_draft(narrative_id, credentials)

            if mra_result.get("error"):
                return dbc.Alert(
                    f"❌ Error generating MRA: {mra_result['error']}", color="danger"
                )

            # Display MRA results
            return dbc.Card(
                [
                    dbc.CardHeader("📄 MRA Draft Generated"),
                    dbc.CardBody(
                        [
                            html.Pre(
                                str(mra_result.get("mra_draft", "No draft generated"))
                            )
                        ]
                    ),
                ]
            )

        except Exception as e:
            return dbc.Alert(f"❌ Error generating MRA: {str(e)}", color="danger")

    return html.Div()


# App Layout
app.layout = dbc.Container(
    [
        dcc.Store(id=CREDENTIALS_STORE),
        dcc.Store(id=WORKFLOW_STORE),
        dcc.Store(id="execution-state-store"),
        dcc.Store(id="analysis-history-store", data=[]),
        # Header
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H1("🧬 KBase Research Agent", className="display-4 mb-4"),
                        html.P(
                            "Automated genome analysis workflows with human approval",
                            className="lead",
                        ),
                    ]
                )
            ],
            className="mb-4",
        ),
        # Main content
        html.Div(
            id="main-content",
            children=[
                create_credentials_form(CREDENTIALS_STORE),
                html.Br(),
                create_analysis_input_form(CREDENTIALS_STORE, WORKFLOW_STORE, run_analysis_planning),
                html.Br(),
                html.Div(id="analysis-results"),
            ],
        ),
    ],
    fluid=True,
)


# Run the app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
