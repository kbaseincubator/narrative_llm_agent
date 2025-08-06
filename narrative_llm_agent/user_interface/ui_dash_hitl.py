import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
import json
import os
from datetime import datetime
from dotenv import find_dotenv, load_dotenv
from langchain.load import dumps, loads
from langchain_core.messages import AIMessage, HumanMessage
from narrative_llm_agent.user_interface.components.credentials import create_credentials_form
from narrative_llm_agent.util.json_util import make_json_serializable
from narrative_llm_agent.agents.metadata_lang import MetadataAgent
from narrative_llm_agent.config import get_llm
from narrative_llm_agent.util.metadata_util import (
    process_metadata_chat,
    check_metadata_completion,
    generate_description_from_metadata,
    extract_metadata_from_conversation,
)
# ----------------------------
# Setup API keys
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Initialize the Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "KBase Research Agent"

# Global variables
analysis_history = []
workflow_instances = {}
metadata_agent_executor = None

CREDENTIALS_STORE = "credentials-store"

# Initialize metadata agent
def initialize_metadata_agent():
    """Initialize the metadata collection agent"""
    llm = get_llm("gpt-4.1-cborg")

    metadata_agent = MetadataAgent(llm=llm)
    global metadata_agent_executor
    if not metadata_agent_executor:
        metadata_agent_executor = metadata_agent.agent_executor
    return metadata_agent_executor

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

def run_analysis_planning(narrative_id, reads_id, description, credentials):
    """Run the analysis planning phase only"""
    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            api_key = credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
        else:
            api_key = credentials.get("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

        # Set environment variables
        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
        if provider == "cborg":
            os.environ["CBORG_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key

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

        # Store workflow instance globally
        workflow_key = f"{narrative_id}_{reads_id}"
        workflow_instances[workflow_key] = workflow

        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": workflow_state,
            "workflow_key": workflow_key,
            "error": workflow_state.get("error"),
            "status": "awaiting_approval" if workflow_state.get("awaiting_approval") else "completed",
        }

    except Exception as e:
        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": None,
            "error": str(e),
            "status": "error",
        }

def run_analysis_execution(workflow_state, credentials, workflow_key=None):
    """Run the analysis execution phase after approval"""
    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            api_key = credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
        else:
            api_key = credentials.get("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

        # Set environment variables
        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
        if provider == "cborg":
            os.environ["CBORG_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key

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
            "status": "completed" if final_state_serializable.get("results") else "error",
        }

    except Exception as e:
        return {"error": str(e), "status": "error"}

def generate_mra_draft(narrative_id, credentials):
    """Generate MRA draft using the MraWriterGraph"""
    try:
        # Set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            api_key = credentials.get("cborg_api_key", os.environ.get("CBORG_API_KEY", ""))
        else:
            api_key = credentials.get("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))

        # Set environment variables
        os.environ["KB_AUTH_TOKEN"] = kb_auth_token
        if provider == "cborg":
            os.environ["CBORG_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key

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

# ----------------------------
# UI Components

def create_metadata_collection_interface():
    """Create the metadata collection interface"""
    return dbc.Card(
        [
            dbc.CardHeader("🔍 Metadata Collection Agent"),
            dbc.CardBody(
                [
                    html.P("Let me help you gather information about your computational biology project."),
                    html.Div("Assistant: Hello! I'm here to help gather information about your computational biology project. Please provide the narrative ID to start.", 
                             id="metadata-response-space"),
                    html.Br(),
                    dcc.Input(
                        id="metadata-input", 
                        type="text", 
                        debounce=True, 
                        placeholder="Type your answer here", 
                        style={"width": "100%", "height": 40}
                    ),
                    html.Br(),
                    html.Br(),
                    dbc.ButtonGroup([
                        dbc.Button("Submit", id="metadata-submit-btn", color="success"),
                        dbc.Button("Clear Chat", id="metadata-clear-btn", color="secondary"),
                        dbc.Button("Start Over", id="metadata-start-btn", color="primary"),
                    ]),
                    html.Br(),
                    html.Br(),
                    html.Div(id="metadata-chat-history", style={
                        "height": "300px", 
                        "overflow-y": "scroll", 
                        "border": "1px solid #ccc", 
                        "padding": "10px",
                        "background-color": "#f8f9fa"
                    }),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "🚀 Proceed to Analysis Planning", 
                                id="proceed-to-analysis-btn", 
                                color="warning", 
                                size="lg",
                                disabled=True
                            ),
                        ], width=6),
                        dbc.Col([
                            dbc.Button(
                                "✅ Force Enable (I have enough info)", 
                                id="force-enable-btn", 
                                color="info", 
                                size="sm",
                                outline=True
                            ),
                        ], width=6),
                    ]),
                    dcc.Store(id="metadata-store", data=[]),
                    dcc.Store(id="collected-metadata", data={}),
                ]
            ),
        ]
    )

def create_input_form():
    """Create the manual input form (kept as backup/override option)"""
    return dbc.Card(
        [
            dbc.CardHeader("📝 Manual Analysis Parameters (Optional Override)"),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Narrative ID"),
                                    dbc.Input(id="narrative-id", type="text"),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Reads ID"),
                                    dbc.Input(id="reads-id", type="text"),
                                ],
                                width=6,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Sequencing Technology"),
                                    dcc.Dropdown(
                                        id="sequencing-tech",
                                        options=[
                                            {"label": "Illumina sequencing", "value": "Illumina sequencing"},
                                            {"label": "PacBio", "value": "PacBio"},
                                            {"label": "Oxford Nanopore", "value": "Oxford Nanopore"},
                                        ],
                                        value="Illumina sequencing",
                                    ),
                                ],
                                width=4,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Organism"),
                                    dbc.Input(id="organism", type="text"),
                                ],
                                width=4,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Genome Type"),
                                    dcc.Dropdown(
                                        id="genome-type",
                                        options=[
                                            {"label": "isolate", "value": "isolate"},
                                            {"label": "metagenome", "value": "metagenome"},
                                            {"label": "transcriptome", "value": "transcriptome"},
                                        ],
                                        value="isolate",
                                    ),
                                ],
                                width=4,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Analysis Description"),
                                    dbc.Textarea(
                                        id="description",
                                        rows=8,
                                        placeholder="Analysis description will be auto-generated from metadata collection...",
                                    ),
                                ]
                            )
                        ],
                        className="mb-3",
                    ),
                    dbc.Button(
                        "🚀 Generate Analysis Plan (Manual)",
                        id="run-analysis-btn",
                        color="success",
                        size="lg",
                    ),
                ]
            ),
        ]
    )

def create_approval_interface(workflow_state):
    """Create the approval interface for the analysis plan"""
    if not workflow_state:
        return html.Div("No workflow state available")

    steps = workflow_state.get("steps_to_run", [])
    if not steps:
        return html.Div("No steps found in workflow state")

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
                html.Td(row["Description"], style={"max-width": "300px"}),
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

    return dbc.Card(
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
                html.Div(analysis_table, className="table-responsive", style={"max-height": "500px", "overflow-y": "auto"}),
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
            ]),
        ],
        className="shadow-sm",
    )

def create_execution_display(execution_result):
    """Create display for execution results"""
    if not execution_result:
        return html.Div()

    components = []

    if execution_result.get("status") == "running":
        components.append(
            dbc.Alert("🔄 Executing analysis workflow... This may take several minutes.", color="info")
        )
    elif execution_result.get("status") == "completed":
        components.append(
            dbc.Alert("✅ Analysis workflow completed successfully!", color="success")
        )

        # Show final results
        final_state = execution_result.get("final_state", {})
        if final_state.get("results"):
            components.append(
                dbc.Card([
                    dbc.CardHeader("🧪 Workflow Results"),
                    dbc.CardBody([html.Pre(str(final_state["results"]))]),
                ], className="mb-3")
            )

        # MRA Generation Button
        components.append(
            dbc.Card([
                dbc.CardHeader("📄 Generate MRA Draft"),
                dbc.CardBody([
                    html.P("Analysis completed successfully! You can now generate a Microbiology Resource Announcements (MRA) draft paper."),
                    dbc.Button("📝 Generate MRA Draft", id="generate-mra-btn", color="primary", size="lg"),
                    html.Div(id="mra-results", className="mt-3"),
                ]),
            ], className="mb-3")
        )

    elif execution_result.get("status") == "error":
        components.append(
            dbc.Alert(f"❌ Error: {execution_result.get('error', 'Unknown error')}", color="danger")
        )

    return html.Div(components)

# ----------------------------
# App Layout

app.layout = dbc.Container([
    dcc.Store(id=CREDENTIALS_STORE),
    dcc.Store(id="workflow-state-store"),
    dcc.Store(id="execution-state-store"),
    dcc.Store(id="analysis-history-store", data=[]),
    
    # Header
    dbc.Row([
        dbc.Col([
            html.H1("🧬 KBase Research Agent", className="display-4 mb-4"),
            html.P("Automated genome analysis workflows with intelligent metadata collection", className="lead"),
        ])
    ], className="mb-4"),
    
    # Main content
    html.Div(id="main-content", children=[
        create_credentials_form(CREDENTIALS_STORE),
        html.Br(),
        
        # Metadata Collection Interface
        create_metadata_collection_interface(),
        html.Br(),
        
        # Manual Input Form (backup/override)
        dbc.Collapse(
            create_input_form(),
            id="manual-form-collapse",
            is_open=False,
        ),
        dbc.Button("Show Manual Input Form", id="toggle-manual-form", color="link", size="sm"),
        html.Br(),
        html.Br(),
        
        # Analysis Results
        html.Div(id="analysis-results"),
    ]),
], fluid=True)

# ----------------------------
# Callbacks

# Force enable button callback
@app.callback(
    Output("proceed-to-analysis-btn", "disabled", allow_duplicate=True),
    Input("force-enable-btn", "n_clicks"),
    prevent_initial_call=True,
)
def force_enable_proceed_button(n_clicks):
    if n_clicks:
        return False  # Enable the button
    return True

# Metadata Collection Chat Callback - Updated to use the imported module
@app.callback(
    [
        Output("metadata-response-space", "children"),
        Output("metadata-store", "data"),
        Output("metadata-input", "value"),
        Output("metadata-chat-history", "children"),
        Output("proceed-to-analysis-btn", "disabled"),
        Output("collected-metadata", "data"),
    ],
    [
        Input("metadata-submit-btn", "n_clicks"),
        Input("metadata-clear-btn", "n_clicks"),
        Input("metadata-start-btn", "n_clicks"),
    ],
    [
        State("metadata-input", "value"),
        State("metadata-store", "data"),
        State(CREDENTIALS_STORE, "data"),
    ],
    prevent_initial_call=True
)
def interact_with_metadata_agent(submit_clicks, clear_clicks, start_clicks, user_input, chat_history, credentials):
    from dash import ctx
    
    try:
        # Initialize metadata agent
        agent_executor = initialize_metadata_agent()
        
        # Handle clear chat
        if ctx.triggered_id == "metadata-clear-btn":
            return "Assistant: Chat cleared. Ready to start over!", [], "", [], True, {}
        
        # Handle start over - let agent initiate conversation
        if ctx.triggered_id == "metadata-start-btn":
            try:
                response = process_metadata_chat(agent_executor, None, [])
                chat_history_obj = [AIMessage(content=response)]
                visual_history = [
                    html.Div([
                        html.Strong("Assistant: "),
                        html.Span(response)
                    ], style={
                        "margin": "5px 0", 
                        "padding": "10px", 
                        "background-color": "#e8f4fd",
                        "border-radius": "5px"
                    })
                ]
                history = dumps(chat_history_obj)
                return f"Assistant: {response}", history, "", visual_history, True, {}
            except Exception as e:
                return f"Error starting conversation: {str(e)}", [], "", [], True, {}
        
        # Handle submit
        if not user_input or not user_input.strip():
            current_history = []
            if chat_history:
                try:
                    chat_history_obj = loads(chat_history) if isinstance(chat_history, str) else chat_history
                    if chat_history_obj:
                        current_history = [html.Div([
                            html.Strong(f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: "),
                            html.Span(msg.content)
                        ], style={"margin": "5px 0", "padding": "5px", "background-color": "#f0f0f0" if isinstance(msg, HumanMessage) else "#e8f4fd"}) 
                        for msg in chat_history_obj]
                except Exception:
                    current_history = []
            
            return "Please enter your response before submitting.", chat_history if chat_history else [], "", current_history, True, {}
        
        # Process the user input using imported functions
        try:
            if chat_history:
                if isinstance(chat_history, str):
                    chat_history_obj = loads(chat_history)
                elif isinstance(chat_history, list):
                    chat_history_obj = chat_history
                else:
                    chat_history_obj = []
            else:
                chat_history_obj = []
            
            response = process_metadata_chat(agent_executor, user_input, chat_history_obj)
            
            # Update chat history
            chat_history_obj.append(HumanMessage(content=user_input))
            chat_history_obj.append(AIMessage(content=response))
            
            # Create visual chat history
            visual_history = []
            for msg in chat_history_obj:
                is_user = isinstance(msg, HumanMessage)
                visual_history.append(
                    html.Div([
                        html.Strong(f"{'User' if is_user else 'Assistant'}: "),
                        html.Span(msg.content)
                    ], style={
                        "margin": "5px 0", 
                        "padding": "10px", 
                        "background-color": "#f0f0f0" if is_user else "#e8f4fd",
                        "border-radius": "5px"
                    })
                )
            
            # Check completion and extract metadata using imported functions
            metadata_complete, collected_data = check_metadata_completion(chat_history_obj)
            
            # Generate description if we have metadata
            if collected_data and not collected_data.get("description"):
                collected_data["description"] = generate_description_from_metadata(collected_data)
            
            history = dumps(chat_history_obj)
            return f"Assistant: {response}", history, "", visual_history, not metadata_complete, collected_data
            
        except Exception as e:
            return f"Error processing request: {str(e)}", chat_history if chat_history else [], user_input, [], True, {}
    
    except Exception as e:
        # Fallback error handling
        return f"Callback error: {str(e)}", [], "", [], True, {}

# Toggle manual form visibility
@app.callback(
    [Output("manual-form-collapse", "is_open"), Output("toggle-manual-form", "children")],
    [Input("toggle-manual-form", "n_clicks")],
    [State("manual-form-collapse", "is_open")],
    prevent_initial_call=True,
)
def toggle_manual_form(n_clicks, is_open):
    if n_clicks:
        return not is_open, "Hide Manual Input Form" if not is_open else "Show Manual Input Form"
    return is_open, "Show Manual Input Form"

# Auto-populate manual form from collected metadata
@app.callback(
    [
        Output("narrative-id", "value"),
        Output("reads-id", "value"),
        Output("sequencing-tech", "value"),
        Output("organism", "value"),
        Output("genome-type", "value"),
        Output("description", "value"),
    ],
    [Input("collected-metadata", "data")],
    prevent_initial_call=True,
)
def populate_form_from_metadata(collected_data):
    if not collected_data:
        return "", "", "Illumina sequencing", "", "isolate", ""
    
    return (
        collected_data.get("narrative_id", ""),
        collected_data.get("reads_id", ""),
        collected_data.get("sequencing_technology", "Illumina sequencing"),
        collected_data.get("organism", ""),
        collected_data.get("genome_type", "isolate"),
        collected_data.get("description", ""),
    )

# Proceed to analysis planning from metadata collection
@app.callback(
    [
        Output("workflow-state-store", "data"),
        Output("analysis-results", "children"),
    ],
    [
        Input("proceed-to-analysis-btn", "n_clicks"),
        Input("run-analysis-btn", "n_clicks"),
    ],
    [
        State(CREDENTIALS_STORE, "data"),
        State("collected-metadata", "data"),
        State("narrative-id", "value"),
        State("reads-id", "value"),
        State("description", "value"),
    ],
    prevent_initial_call=True,
)
def run_analysis_planning_callback(proceed_clicks, manual_clicks, credentials, collected_metadata, manual_narrative_id, manual_reads_id, manual_description):
    ctx = callback_context
    if not ctx.triggered:
        return {}, html.Div()
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if not credentials or not credentials.get("kb_auth_token"):
        return {}, dbc.Alert("Please configure your credentials first.", color="warning")
    
    # Determine source of data (metadata collection vs manual input)
    if button_id == "proceed-to-analysis-btn" and proceed_clicks and collected_metadata:
        narrative_id = collected_metadata.get("narrative_id")
        reads_id = collected_metadata.get("reads_id")
        description = collected_metadata.get("description")
        source = "Metadata Collection Agent"
    elif button_id == "run-analysis-btn" and manual_clicks:
        narrative_id = manual_narrative_id or "217789"
        reads_id = manual_reads_id or "217789/2/1"
        description = manual_description
        source = "Manual Input"
        
        # Ensure description is valid
        if not description or description.strip() == "":
            description = """The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology: Illumina sequencing
organism: Bacillus subtilis sp. strain UAMC
genome type: isolate

I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from Illumina sequencing for a isolate genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe."""
    else:
        return {}, html.Div()
    
    if not narrative_id or not reads_id:
        return {}, dbc.Alert("Missing narrative ID or reads ID. Please complete metadata collection or manual input.", color="warning")
    
    # Run the analysis planning
    result = run_analysis_planning(narrative_id, reads_id, description, credentials)
    
    # Update analysis history
    global analysis_history
    analysis_history.append({
        "timestamp": datetime.now().isoformat(),
        "narrative_id": narrative_id,
        "reads_id": reads_id,
        "status": result.get("status", "unknown"),
        "error": result.get("error"),
        "source": source,
    })
    
    # Create appropriate display based on result
    if result.get("status") == "awaiting_approval":
        display_component = dbc.Card([
            dbc.CardHeader(f"✅ Analysis Plan Generated (via {source})"),
            dbc.CardBody([
                dbc.Alert(f"Successfully generated analysis plan using data from: {source}", color="success"),
                create_approval_interface(result["workflow_state"])
            ])
        ])
        return result, display_component
    
    elif result.get("status") == "error":
        error_component = dbc.Alert(f"❌ Error: {result.get('error', 'Unknown error')}", color="danger")
        return result, error_component
    else:
        unknown_component = dbc.Alert(f"⚠️ Unexpected status: {result.get('status')}", color="warning")
        return result, unknown_component

# Handle approval actions
@app.callback(
    [Output("execution-state-store", "data"), Output("approval-status", "children")],
    [
        Input("approve-btn", "n_clicks"),
        Input("reject-btn", "n_clicks"),
        Input("cancel-btn", "n_clicks"),
    ],
    [State("workflow-state-store", "data"), State(CREDENTIALS_STORE, "data")],
    prevent_initial_call=True,
)
def handle_approval(approve_clicks, reject_clicks, cancel_clicks, workflow_state, credentials):
    ctx = callback_context
    if not ctx.triggered:
        return {}, html.Div()

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "approve-btn" and approve_clicks:
        loading_status = dbc.Alert("🔄 Executing approved workflow... Please wait.", color="info")

        try:
            # Get the nested workflow state and update it properly
            inner_workflow_state = workflow_state.get("workflow_state", {})
            inner_workflow_state["human_approval_status"] = "approved"
            inner_workflow_state["awaiting_approval"] = False
            inner_workflow_state["input_object_upa"] = workflow_state.get("reads_id")

            # Execute the workflow
            execution_result = run_analysis_execution(
                workflow_state.get("workflow_state", {}),
                credentials,
                workflow_state.get("workflow_key"),
            )

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

# Display execution results
@app.callback(
    Output("analysis-results", "children", allow_duplicate=True),
    Input("execution-state-store", "data"),
    State("analysis-results", "children"),
    prevent_initial_call=True,
)
def display_execution_results(execution_state, current_results):
    if not execution_state:
        return current_results

    execution_display = create_execution_display(execution_state)
    return execution_display

# Handle feedback submission
@app.callback(
    Output("approval-status", "children", allow_duplicate=True),
    Input("submit-feedback-btn", "n_clicks"),
    State("feedback-text", "value"),
    prevent_initial_call=True,
)
def handle_feedback_submission(n_clicks, feedback_text):
    if n_clicks:
        print("=== USER FEEDBACK ===")
        print(f"Feedback: {feedback_text}")
        print("=" * 25)

        return dbc.Alert([
            html.I(className="bi bi-chat-dots me-2"),
            "Thank you for your feedback. Please modify the analysis parameters and try again.",
        ], color="info")

    return html.Div()

# MRA generation callback
@app.callback(
    Output("mra-results", "children"),
    Input("generate-mra-btn", "n_clicks"),
    [State(CREDENTIALS_STORE, "data"), State("narrative-id", "value"), State("collected-metadata", "data")],
    prevent_initial_call=True,
)
def generate_mra(n_clicks, credentials, manual_narrative_id, collected_metadata):
    if not n_clicks or n_clicks == 0:
        return html.Div()
    
    if n_clicks and credentials and credentials.get("kb_auth_token"):
        # Get narrative ID from collected metadata or manual input
        narrative_id = None
        if collected_metadata and collected_metadata.get("narrative_id"):
            narrative_id = collected_metadata["narrative_id"]
        elif manual_narrative_id:
            narrative_id = manual_narrative_id
        
        if not narrative_id:
            return dbc.Alert("❌ No narrative ID available for MRA generation", color="danger")

        try:
            # Generate MRA draft
            mra_result = generate_mra_draft(narrative_id, credentials)

            if mra_result.get("error"):
                return dbc.Alert(f"❌ Error generating MRA: {mra_result['error']}", color="danger")

            return dbc.Card([
                dbc.CardHeader("📄 MRA Draft Generated"),
                dbc.CardBody([
                    html.Pre(str(mra_result.get("mra_draft", "No draft generated")))
                ]),
            ])

        except Exception as e:
            return dbc.Alert(f"❌ Error generating MRA: {str(e)}", color="danger")

    return html.Div()

# ----------------------------
# Launch App

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8050)