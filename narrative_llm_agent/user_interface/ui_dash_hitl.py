import json
from io import StringIO
import uuid
from ansi2html import Ansi2HTMLConverter
import dash
from dash import ctx, dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from dash_extensions import Purify
import os
from dotenv import find_dotenv, load_dotenv
from langchain.load import dumps, loads
from langchain_core.messages import AIMessage, HumanMessage
from narrative_llm_agent.user_interface.components.credentials import (
    create_credentials_form,
)
from narrative_llm_agent.user_interface.components.analysis_setup import (
    StreamRedirector,
    create_analysis_input_form,
    create_analysis_output_display,
)
from narrative_llm_agent.user_interface.components.analysis_approval import (
    create_approval_interface,
)
from narrative_llm_agent.user_interface.components.metadata_agent_format import (
    format_agent_response,
)
from narrative_llm_agent.agents.metadata_lang import MetadataAgent
from narrative_llm_agent.config import get_llm
from narrative_llm_agent.util.metadata_util import (
    check_metadata_completion,
    generate_description_from_metadata,
    process_metadata_chat,
)
from narrative_llm_agent.user_interface.constants import (
    CREDENTIALS_STORE,
    SESSION_ID_STORE,
    WORKFLOW_INSTANCES,
)
from narrative_llm_agent.user_interface.kbase_loader import load_kbase_classes
from datetime import datetime

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
metadata_agent_executor = None


# Initialize metadata agent
def initialize_metadata_agent(credentials):
    """Initialize the metadata collection agent"""

    # Get credentials and set environment variables
    kb_auth_token = credentials.get("kb_auth_token", "")
    provider = credentials.get("provider", "openai")

    if provider == "cborg":
        api_key = credentials.get("cborg_api_key")
        used_llm = "gpt-4.1-cborg"
    else:
        api_key = credentials.get("openai_api_key")
        used_llm = "gpt-4o-openai"

    llm = get_llm(used_llm, api_key=api_key)
    print(f"Using LLM: {used_llm} with API key: {api_key}")
    metadata_agent = MetadataAgent(llm=llm, token=kb_auth_token)
    global metadata_agent_executor
    if not metadata_agent_executor:
        metadata_agent_executor = metadata_agent.agent_executor
    return metadata_agent_executor


def run_analysis_planning(narrative_id, reads_id, description, credentials):
    """Run the analysis planning phase only"""

    try:
        # Get credentials and set environment variables
        kb_auth_token = credentials.get("kb_auth_token", "")
        provider = credentials.get("provider", "openai")

        if provider == "cborg":
            api_key = credentials.get("cborg_api_key")
            used_llm = "gpt-4.1-cborg"
        else:
            api_key = credentials.get("openai_api_key")
            used_llm = "gpt-4o-openai"

        # Set Neo4j environment variables if they exist
        # TODO: should probably be globally set at startup.
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
            analyst_llm=used_llm,
            analyst_token=api_key,
            app_flow_llm=used_llm,
            app_flow_token=api_key,
            kbase_token=kb_auth_token,
        )

        # Run the planning phase only
        workflow_state = workflow.run(
            narrative_id=narrative_id, reads_id=reads_id, description=description
        )
        # Store workflow instance globally
        workflow_key = f"{narrative_id}_{reads_id}"
        WORKFLOW_INSTANCES[workflow_key] = workflow

        return {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "workflow_state": workflow_state,
            "workflow_key": workflow_key,
            "error": workflow_state.get("error"),
            "status": "awaiting_approval"
            if workflow_state.get("awaiting_approval")
            else "completed",
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


def generate_mra_draft(narrative_id: int, credentials: dict[str, str]):
    """Generate MRA draft using the MraWriterGraph"""
    kbase_token = credentials.get("kb_auth_token")
    provider = credentials.get("provider")
    if provider == "cborg":
        api_key = credentials.get("cborg_api_key")
        writer_llm = "gpt-o1-cborg"
    else:
        api_key = credentials.get("openai_api_key")
        writer_llm = "gpt-o1-openai"

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
        mra_writer = MraWriterGraph(
            ws_client, ee_client, writer_llm, writer_token=api_key, token=kbase_token
        )

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
                    html.P(
                        "Let me help you gather information about your computational biology project."
                    ),
                    html.Div(
                        "Assistant: Hello! I'm here to help gather information about your computational biology project. Please provide the narrative ID to start.",
                        id="metadata-response-space",
                    ),
                    html.Br(),
                    dcc.Input(
                        id="metadata-input",
                        type="text",
                        debounce=True,
                        placeholder="Type your answer here",
                        style={"width": "100%", "height": 40},
                    ),
                    html.Br(),
                    html.Br(),
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                "Submit", id="metadata-submit-btn", color="success"
                            ),
                            dbc.Button(
                                "Clear Chat", id="metadata-clear-btn", color="secondary"
                            ),
                            dbc.Button(
                                "Start Over", id="metadata-start-btn", color="primary"
                            ),
                        ]
                    ),
                    html.Br(),
                    html.Br(),
                    html.Div(
                        id="metadata-chat-history",
                        style={
                            "height": "300px",
                            "overflowY": "scroll",
                            "border": "1px solid #ccc",
                            "padding": "10px",
                            "backgroundColor": "#f8f9fa",
                        },
                    ),
                    html.Hr(),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Button(
                                        "🚀 Proceed to Analysis Planning",
                                        id="proceed-to-analysis-btn",
                                        color="warning",
                                        size="lg",
                                        disabled=True,
                                    ),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Button(
                                        "✅ Force Enable (I have enough info)",
                                        id="force-enable-btn",
                                        color="info",
                                        size="sm",
                                        outline=True,
                                    ),
                                ],
                                width=6,
                            ),
                        ]
                    ),
                    dcc.Store(id="metadata-store", data=[]),
                    dcc.Store(id="collected-metadata", data={}),
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


# ----------------------------
# App Layout

def create_main_layout():
    session_id = str(uuid.uuid4())
    layout = dbc.Container(
        [
            dcc.Store(id=CREDENTIALS_STORE),
            dcc.Store(id="workflow-state-store"),
            dcc.Store(id="execution-state-store"),
            dcc.Store(id="analysis-history-store", data=[]),
            dcc.Store(id=SESSION_ID_STORE, data=session_id),
            # Header
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H1("🧬 KBase Research Agent", className="display-4 mb-4"),
                            html.P(
                                "Automated genome analysis workflows with intelligent metadata collection",
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
                    create_credentials_form(),
                    html.Br(),
                    # Metadata Collection Interface
                    create_metadata_collection_interface(),
                    html.Br(),
                    # Manual Input Form (backup/override)
                    dbc.Collapse(
                        create_analysis_input_form(run_analysis_planning),
                        id="manual-form-collapse",
                        is_open=False,
                    ),
                    dbc.Button(
                        "Show Manual Input Form",
                        id="toggle-manual-form",
                        color="link",
                        size="sm",
                    ),
                    html.Br(),
                    create_analysis_output_display(),
                    html.Br(),
                    # Analysis Results
                    html.Div(id="analysis-results"),
                ],
            ),
        ],
        fluid=True,
    )
    return layout

app.layout = create_main_layout()

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
    prevent_initial_call=True,
)
def interact_with_metadata_agent(
    submit_clicks, clear_clicks, start_clicks, user_input, chat_history, credentials
):
    try:
        # Initialize metadata agent
        agent_executor = initialize_metadata_agent(credentials=credentials)

        # Handle clear chat
        if ctx.triggered_id == "metadata-clear-btn":
            return (
                format_agent_response("Assistant: Chat cleared. Ready to start over!"),
                [],
                "",
                [],
                True,
                {},
            )

        # Handle start over
        if ctx.triggered_id == "metadata-start-btn":
            try:
                response = process_metadata_chat(agent_executor, None, [])
                chat_history_obj = [AIMessage(content=response)]
                # Format the response for visual display
                formatted_response = format_agent_response(response)
                visual_history = [
                    html.Div(
                        [html.Strong("Assistant: "), html.Span(response)],
                        style={
                            "margin": "5px 0",
                            "padding": "10px",
                            "backgroundColor": "#e8f4fd",
                            "borderRadius": "5px",
                        },
                    )
                ]
                history = dumps(chat_history_obj)
                return formatted_response, history, "", visual_history, True, {}
            except Exception as e:
                return f"Error starting conversation: {str(e)}", [], "", [], True, {}

        # Handle submit
        if not user_input or not user_input.strip():
            current_history = []
            if chat_history:
                try:
                    chat_history_obj = (
                        loads(chat_history)
                        if isinstance(chat_history, str)
                        else chat_history
                    )
                    if chat_history_obj:
                        current_history = [
                            html.Div(
                                [
                                    html.Strong(
                                        f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: "
                                    ),
                                    html.Span(msg.content),
                                ],
                                style={
                                    "margin": "5px 0",
                                    "padding": "5px",
                                    "backgroundColor": "#f0f0f0"
                                    if isinstance(msg, HumanMessage)
                                    else "#e8f4fd",
                                },
                            )
                            for msg in chat_history_obj
                        ]
                except Exception:
                    current_history = []

            return (
                "Please enter your response before submitting.",
                chat_history if chat_history else [],
                "",
                current_history,
                True,
                {},
            )

        # Process the user input
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

            response = process_metadata_chat(
                agent_executor, user_input, chat_history_obj
            )

            # Update chat history
            chat_history_obj.append(HumanMessage(content=user_input))
            chat_history_obj.append(AIMessage(content=response))

            # Create visual chat history
            visual_history = []
            for msg in chat_history_obj:
                is_user = isinstance(msg, HumanMessage)
                content = msg.content if is_user else format_agent_response(msg.content)

                visual_history.append(
                    html.Div(
                        [
                            html.Strong(
                                f"{'User' if is_user else 'Assistant'}: ",
                                className="text-primary" if is_user else "text-info",
                            ),
                            html.Span(content) if is_user else content,
                        ],
                        style={
                            "margin": "5px 0",
                            "padding": "15px",
                            "backgroundColor": "#f8f9fa" if is_user else "#e8f4fd",
                            "borderRadius": "8px",
                            "border": f"1px solid {'#dee2e6' if is_user else '#bee5eb'}",
                        },
                    )
                )

            # Check completion and extract metadata using imported functions
            metadata_complete, collected_data = check_metadata_completion(
                chat_history_obj
            )

            # Generate description if we have metadata
            if collected_data and not collected_data.get("description"):
                collected_data["description"] = generate_description_from_metadata(
                    collected_data
                )
            formatted_response = format_agent_response(response)
            history = dumps(chat_history_obj)
            return_val = (
                formatted_response,
                history,
                "",
                visual_history,
                not metadata_complete,
                collected_data,
            )
            print("returning from metadata agent")
            print(return_val)
            return return_val

        except Exception as e:
            return (
                f"Error processing request: {str(e)}",
                chat_history if chat_history else [],
                user_input,
                [],
                True,
                {},
            )

    except Exception as e:
        # Fallback error handling
        print(e)
        return f"Callback error: {str(e)}", [], "", [], True, {}


# Toggle manual form visibility
@app.callback(
    [
        Output("manual-form-collapse", "is_open"),
        Output("toggle-manual-form", "children"),
    ],
    [Input("toggle-manual-form", "n_clicks")],
    [State("manual-form-collapse", "is_open")],
    prevent_initial_call=True,
)
def toggle_manual_form(n_clicks, is_open):
    if n_clicks:
        return (
            not is_open,
            "Hide Manual Input Form" if not is_open else "Show Manual Input Form",
        )
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


@app.callback(
    [Output("auto-analysis-log-poller", "disabled"),
     Output("auto-analysis-container", "style")],
    [Input("proceed-to-analysis-btn", "n_clicks")],
    prevent_initial_call=True,
)
def start_analysis_poller(n_clicks):
    print("starting analysis poller")
    return (False if n_clicks else True), {}


analysis_log_buffer = StringIO()


@app.callback(
    [
        Output("auto-analysis-log-output", "children"),
        Output("auto-analysis-scroll-trigger", "data"),
    ],
    [
        Input("auto-analysis-log-poller", "n_intervals"),
    ],
    prevent_initial_call=True,
)
def update_log(_):
    print("updating analysis log")
    log_value = analysis_log_buffer.getvalue()
    html_value = Ansi2HTMLConverter(inline=True).convert(log_value, full=False)
    return Purify(html=(f"<div>{html_value}</div>")), {"scroll": True}


# here we run the analysis planning callback
# Proceed to analysis planning from metadata collection
@app.callback(
    [
        Output("workflow-state-store", "data"),
        Output("analysis-results", "children"),
        Output("auto-analysis-log-poller", "disabled", allow_duplicate=True)
    ],
    [
        Input("proceed-to-analysis-btn", "n_clicks"),
    ],
    [
        State(CREDENTIALS_STORE, "data"),
        State("collected-metadata", "data"),
        State(SESSION_ID_STORE, "data")
    ],
    prevent_initial_call=True,
)
def run_analysis_planning_callback(proceed_clicks, credentials, collected_metadata, session_id):
    ctx = callback_context
    if not ctx.triggered:
        return {}, html.Div(), True

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if not credentials or not credentials.get("kb_auth_token"):
        return {}, dbc.Alert(
            "Please configure your credentials first.", color="warning"
        ), True

    # Determine source of data (metadata collection vs manual input)
    if button_id == "proceed-to-analysis-btn" and proceed_clicks: # and collected_metadata:
        narrative_id = collected_metadata.get("narrative_id")
        reads_id = collected_metadata.get("reads_id")
        description = collected_metadata.get("description")
        source = "Metadata Collection Agent"

        # Ensure description is valid
        if not description or description.strip() == "":
            description = """The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology: Illumina sequencing
organism: Bacillus subtilis sp. strain UAMC
genome type: isolate

I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from Illumina sequencing for a isolate genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe."""
    else:
        return {}, html.Div(), True

    if not narrative_id or not reads_id:
        return {}, dbc.Alert(
            "Missing narrative ID or reads ID. Please complete metadata collection or manual input.",
            color="warning",
        ), True

    # Run the analysis planning
    with StreamRedirector(analysis_log_buffer):
        print("Starting KBase workflow planning")
        # with open(os.path.dirname(os.path.abspath(__file__)) + "/temp.json") as in_json:
        #     result = json.load(in_json)
        result = run_analysis_planning(narrative_id, reads_id, description, credentials)



    # Update analysis history
    global analysis_history
    analysis_history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "status": result.get("status", "unknown"),
            "error": result.get("error"),
            "source": source,
        }
    )

    # Create appropriate display based on result
    if result.get("status") == "awaiting_approval":
        display_component = dbc.Card(
            [
                dbc.CardHeader(f"✅ Analysis Plan Generated (via {source})"),
                dbc.CardBody(
                    [
                        dbc.Alert(
                            f"Successfully generated analysis plan using data from: {source}",
                            color="success",
                        ),
                        create_approval_interface(result["workflow_state"], session_id),
                    ]
                ),
            ]
        )
        return result, display_component, True

    elif result.get("status") == "error":
        error_component = dbc.Alert(
            f"❌ Error: {result.get('error', 'Unknown error')}", color="danger"
        )
        return result, error_component, True
    else:
        unknown_component = dbc.Alert(
            f"⚠️ Unexpected status: {result.get('status')}", color="warning"
        )
        return result, unknown_component, True


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

        return dbc.Alert(
            [
                html.I(className="bi bi-chat-dots me-2"),
                "Thank you for your feedback. Please modify the analysis parameters and try again.",
            ],
            color="info",
        )

    return html.Div()


# MRA generation callback
@app.callback(
    Output("mra-results", "children"),
    Input("generate-mra-btn", "n_clicks"),
    [State(CREDENTIALS_STORE, "data"), State("collected-metadata", "data")],
    prevent_initial_call=True,
)
def generate_mra(n_clicks, credentials, collected_metadata):
    if not n_clicks or n_clicks == 0:
        return html.Div()

    if n_clicks and credentials and credentials.get("kb_auth_token"):
        # Get narrative ID from collected metadata or manual input
        narrative_id = None
        if collected_metadata and collected_metadata.get("narrative_id"):
            narrative_id = collected_metadata["narrative_id"]

        if not narrative_id:
            return dbc.Alert(
                "❌ No narrative ID available for MRA generation", color="danger"
            )

        try:
            # Generate MRA draft
            mra_result = generate_mra_draft(narrative_id, credentials)

            if mra_result.get("error"):
                return dbc.Alert(
                    f"❌ Error generating MRA: {mra_result['error']}", color="danger"
                )

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


# ----------------------------
# Launch App
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
