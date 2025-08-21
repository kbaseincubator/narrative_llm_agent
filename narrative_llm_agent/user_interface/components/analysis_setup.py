from datetime import datetime
import io
import sys
from typing import Callable
import dash_bootstrap_components as dbc
from dash import callback_context, dcc, html, Input, Output, callback, State
from ansi2html import Ansi2HTMLConverter
from dash_extensions import Purify

from narrative_llm_agent.user_interface.components.analysis_approval import create_approval_interface
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE, WORKFLOW_STORE

def analysis_prompt(seq_tech: str, org_name: str, genome_type: str):
    return f"""The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing technology: {seq_tech}
organism: {org_name}
genome type: {genome_type}

I want you to generate an analysis plan for annotating the uploaded paired-end reads obtained from {seq_tech} for a {genome_type} genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe."""

class StreamRedirector:
    def __init__(self, target):
        self.target = target
        self._stdout = sys.stdout

    def __enter__(self):
        sys.stdout = self.target
    def __exit__(self, *args):
        sys.stdout = self._stdout

# In-memory buffer
log_buffer = io.StringIO()
converter = Ansi2HTMLConverter(inline=True)

def create_analysis_input_form(analysis_fn: Callable):
    layout = dbc.Card(
        [
            dbc.CardHeader("📝 Manual Analysis Parameters (Optional Override)"),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Narrative ID"),
                                    dbc.Input(
                                        id="narrative-id", type="text"
                                    ),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Reads ID"),
                                    dbc.Input(
                                        id="reads-id", type="text"
                                    ),
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
                                            {
                                                "label": "Illumina sequencing",
                                                "value": "Illumina sequencing",
                                            },
                                            {"label": "PacBio", "value": "PacBio"},
                                            {
                                                "label": "Oxford Nanopore",
                                                "value": "Oxford Nanopore",
                                            },
                                        ],
                                        value="Illumina sequencing",
                                    ),
                                ],
                                width=4,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Organism"),
                                    dbc.Input(
                                        id="organism",
                                        type="text",
                                    ),
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
                                            {
                                                "label": "metagenome",
                                                "value": "metagenome",
                                            },
                                            {
                                                "label": "transcriptome",
                                                "value": "transcriptome",
                                            },
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
                                        placeholder="Analysis description will be auto-generated from metadata collection..."
                                    ),
                                ]
                            )
                        ],
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Button(
                                        "🚀 Generate Analysis Plan (Manual)",
                                        id="run-analysis-btn",
                                        color="success",
                                        size="lg",
                                    ),

                                ]
                            )
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Alert("Running analysis!", id="analysis-status-message"),
                                    html.Div([
                                        dcc.Interval(id="log-poller", interval=1000, disabled=True),
                                        dcc.Store(id="analysis-scroll-trigger"),
                                        html.Div(
                                            id="log-output",
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
                                    ]),
                                ]
                            )
                        ],
                        id="analysis-status",
                        style={"display": "none"},
                        class_name="mt-3"
                    )
                ]
            ),
        ]
    )


    @callback(
        [
            Output("analysis-status", "style"),
            Output("analysis-status-message", "children"),
            Output("run-analysis-btn", "disabled"),
            Output("log-poller", "disabled")

        ],
        Input("run-analysis-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def analysis_start_button_click(n_clicks):
        """
        Display 'analysis running' message
        """
        return {}, "Running analysis!", True, False

    @callback(
        Output("log-output", "children"),
        Output("analysis-scroll-trigger", "data"),
        Input("log-poller", "n_intervals"),
    )
    def update_log(_):
        log_value = log_buffer.getvalue()
        html_value = converter.convert(log_value, full=False)
        return Purify(html=(f"<div>{html_value}</div>")), {"scroll": True}

    # # Callback for running analysis planning
    # @callback(
    #     [
    #         Output(WORKFLOW_STORE, "data"),
    #         Output("analysis-results", "children"),
    #     ],  # Remove the analysis-loading output
    #     [
    #         #Input("proceed-to-analysis-btn", "n_clicks"),
    #         Input("run-analysis-btn", "n_clicks"),
    #     ],
    #     [
    #         State(CREDENTIALS_STORE, "data"),
    #         #State("collected-metadata", "data"),
    #         State("narrative-id", "value"),
    #         State("reads-id", "value"),
    #         State("description", "value"),
    #     ],
    #     prevent_initial_call=True,
    # )
    # def run_analysis_planning_callback(manual_clicks: int, credentials, narrative_id: str, reads_id: str, manual_description: str
    # ):
    #     ctx = callback_context
    #     if not ctx.triggered:
    #         return {}, html.Div()

    #     button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    #     if not credentials or not credentials.get("kb_auth_token"):
    #         return {}, dbc.Alert("Please configure your credentials first.", color="warning")
    #     # if button_id == "proceed-to-analysis-btn" and proceed_clicks and collected_metadata:
    #     #     narrative_id = collected_metadata.get("narrative_id")
    #     #     reads_id = collected_metadata.get("reads_id")
    #     #     description = collected_metadata.get("description")
    #     #     source = "Metadata Collection Agent"
    #     # elif button_id == "run-analysis-btn" and manual_clicks:
    #     #     narrative_id = narrative_id or "217789"
    #     #     reads_id = reads_id or "217789/2/1"
    #     #     description = manual_description
    #     #     source = "Manual Input"
    #     # else:
    #     #     return {}, html.Div()
    #     # Use manual input values
    #     narrative_id = narrative_id or "217789"
    #     reads_id = reads_id or "217789/2/1"
    #     description = manual_description
    #     source = "Manual Input"
    #     if not description or not description.strip():
    #         # fail here.
    #         return {"error": "No analysis prompt found"}, dbc.Alert(
    #             "Error: No analysis prompt found!", color="danger"
    #         )

    #     if not narrative_id or not reads_id:
    #         return {}, dbc.Alert("Missing narrative ID or reads ID. Please complete metadata collection or manual input.", color="warning")

    #     print('starting analysis runner')
    #     def analysis_runner():
    #         return analysis_fn(narrative_id, reads_id, description, credentials)

    #     # Run the analysis planning
    #     with StreamRedirector(log_buffer):
    #         print(datetime.now())
    #         print(narrative_id)
    #         print(reads_id)
    #         print(description)
    #         # TODO: convert to thread
    #         result = analysis_runner()

    #     # Create appropriate display based on result
    #     if result.get("status") == "awaiting_approval":
    #         display_component = dbc.Card([
    #             dbc.CardHeader(f"✅ Analysis Plan Generated (via {source})"),
    #             dbc.CardBody([
    #                 dbc.Alert(f"Successfully generated analysis plan using data from: {source}", color="success"),
    #                 create_approval_interface(result["workflow_state"])
    #             ])
    #         ])
    #         return result, display_component

    #     elif result.get("status") == "error":
    #         error_component = dbc.Alert(f"❌ Error: {result.get('error', 'Unknown error')}", color="danger")
    #         return result, error_component
    #     else:
    #         unknown_component = dbc.Alert(f"⚠️ Unexpected status: {result.get('status')}", color="warning")
    #         return result, unknown_component

    return layout


def create_analysis_output_display():
    layout = dbc.Card(
        [
            dbc.CardHeader("Workflow analysis processing"),
            dbc.CardBody([
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Div([
                                    dcc.Interval(id="auto-analysis-log-poller", interval=1000, disabled=True),
                                    dcc.Store(id="auto-analysis-scroll-trigger"),
                                    html.Div(
                                        id="auto-analysis-log-output",
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
                                ]),
                            ]
                        )
                    ],
                    id="auto-analysis-status",
                    class_name="mt-3"
                )
            ])
        ],
        id="auto-analysis-container",
        style={"display": "none"}
    )

    return layout
