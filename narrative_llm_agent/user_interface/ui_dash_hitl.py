from io import StringIO
import uuid
from ansi2html import Ansi2HTMLConverter
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from dash_extensions import Purify
from dotenv import find_dotenv, load_dotenv
from narrative_llm_agent.user_interface.components.credentials import (
    create_credentials_form,
)
from narrative_llm_agent.user_interface.components.analysis_setup import (
    StreamRedirector,
    create_analysis_output_display,
)
from narrative_llm_agent.user_interface.components.analysis_approval import (
    create_approval_interface,
)
from narrative_llm_agent.user_interface.components.metadata import create_metadata_collection_interface
from narrative_llm_agent.user_interface.components.narrative_data import narrative_data_dropdown
from narrative_llm_agent.user_interface.workflow_runners import generate_mra_draft, run_analysis_planning
from narrative_llm_agent.user_interface.constants import (
    CREDENTIALS_LOCAL_STORE,
    CREDENTIALS_STORE,
    DATA_SELECTION_STORE,
    METADATA_STORE,
    SESSION_ID_STORE,
)
from datetime import datetime

# TODO: move this somewhere else
ANALYSIS_LOG_BUFFERS = {}

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
# TODO: this should be a log file or something. It doesn't appear to be used, just written to.
analysis_history = []

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
            dcc.Store(id=CREDENTIALS_LOCAL_STORE, storage_type="local"),
            dcc.Store(id=DATA_SELECTION_STORE),
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
                    narrative_data_dropdown(),
                    create_metadata_collection_interface(),
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


@app.callback(
    [Output("auto-analysis-log-poller", "disabled"),
     Output("auto-analysis-container", "style")],
    [Input("proceed-to-analysis-btn", "n_clicks")],
    prevent_initial_call=True,
)
def start_analysis_poller(n_clicks):
    print("starting analysis poller")
    return (False if n_clicks else True), {}


@app.callback(
    [
        Output("auto-analysis-log-output", "children"),
        Output("auto-analysis-scroll-trigger", "data"),
    ],
    [
        Input("auto-analysis-log-poller", "n_intervals"),
    ],
    [
        State(SESSION_ID_STORE, "data")
    ],
    prevent_initial_call=True,
)
def update_log(_, session_id):
    if session_id in ANALYSIS_LOG_BUFFERS:
        log_value = ANALYSIS_LOG_BUFFERS[session_id].getvalue()
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
        State(METADATA_STORE, "data"),
        State(SESSION_ID_STORE, "data")
    ],
    prevent_initial_call=True,
)
def run_analysis_planning_callback(proceed_clicks, credentials, collected_metadata, session_id):
    if session_id not in ANALYSIS_LOG_BUFFERS:
        ANALYSIS_LOG_BUFFERS[session_id] = StringIO()

    if not callback_context.triggered:
        return {}, html.Div(), True

    button_id = callback_context.triggered[0]["prop_id"].split(".")[0]

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

I want you to generate an analysis plan for annotating the uploaded paired-end reads obtained from Illumina sequencing for a isolate genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe."""
    else:
        return {}, html.Div(), True

    if not narrative_id or not reads_id:
        return {}, dbc.Alert(
            "Missing narrative ID or reads ID. Please complete metadata collection.",
            color="warning",
        ), True

    # Run the analysis planning
    with StreamRedirector(ANALYSIS_LOG_BUFFERS[session_id]):
        print("Starting KBase workflow planning")
        # with open(os.path.dirname(os.path.abspath(__file__)) + "/temp.json") as in_json:
        #     result = json.load(in_json)
        result = run_analysis_planning(narrative_id, reads_id, description, credentials)

    del ANALYSIS_LOG_BUFFERS[session_id]

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
    [State(CREDENTIALS_STORE, "data"), State(METADATA_STORE, "data")],
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
