from contextlib import redirect_stdout
from datetime import datetime
import io
import sys
from typing import Callable
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback, State
from threading import Thread

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



def create_analysis_input_form(credentials_store: str, workflow_store: str, analysis_fn: Callable):
    layout = dbc.Card(
        [
            dbc.CardHeader("📝 Analysis Parameters"),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Narrative ID"),
                                    dbc.Input(
                                        id="narrative-id", value="217789", type="text"
                                    ),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Reads ID"),
                                    dbc.Input(
                                        id="reads-id", value="217789/2/1", type="text"
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
                                        value="Bacillus subtilis sp. strain UAMC",
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
                                        placeholder="Enter analysis description..."
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
                                        "🚀 Generate Analysis Plan",
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
                                    dcc.Interval(id="log-poller", interval=1000, disabled=True),
                                    html.Pre(
                                        id="log-output",
                                        style={
                                            "whiteSpace": "pre-wrap",
                                            "height": "300px",
                                            "overflowY": "auto"
                                        }
                                    ),
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


    # Callback for updating description based on inputs
    @callback(
        Output("description", "value"),
        [
            Input("sequencing-tech", "value"),
            Input("organism", "value"),
            Input("genome-type", "value"),
        ],
    )
    def update_description(sequencing_tech, organism, genome_type):
        return analysis_prompt(sequencing_tech, organism, genome_type)

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
        Input("log-poller", "n_intervals"),
    )
    def update_log(_):
        return log_buffer.getvalue()


    # Callback for running analysis planning
    @callback(
        [
            Output(workflow_store, "data"),
            Output("analysis-results", "children"),
        ],  # Remove the analysis-loading output
        Input("run-analysis-btn", "n_clicks"),
        [
            State(credentials_store, "data"),
            State("narrative-id", "value"),
            State("reads-id", "value"),
            State("description", "value"),
        ],
        prevent_initial_call=True,
    )
    def run_analysis_planning_callback(
        n_clicks: int, credentials: dict[str, str], narrative_id: str, reads_id: str, description: str
    ):
        if n_clicks and credentials and credentials.get("kb_auth_token"):
            # Validate inputs and provide defaults
            narrative_id = narrative_id or "217789"
            reads_id = reads_id or "217789/2/1"

            if not description.strip():
                # fail here.
                return {"error": "No analysis prompt found"}, dbc.Alert(
                    "Error: No analysis prompt found!", color="danger"
                )

            def analysis_runner():
                return analysis_fn(narrative_id, reads_id, description, credentials)

            # Run the analysis planning
            with StreamRedirector(log_buffer):
                print(narrative_id)
                print(reads_id)
                print(description)
                Thread(target=analysis_runner, daemon=True)
                # result = analysis_fn(narrative_id, reads_id, description, credentials)

            # # Create appropriate display based on result
            # if result.get("status") == "awaiting_approval":
            #     display_component = dbc.Alert("Done!")
            #     # display_component = create_approval_interface(result["workflow_state"])
            #     return result, display_component

            # elif result.get("status") == "error":
            #     error_component = dbc.Alert(
            #         f"❌ Error: {result.get('error', 'Unknown error')}", color="danger"
            #     )
            #     return result, error_component
            # else:
            #     unknown_component = dbc.Alert(
            #         f"⚠️ Unexpected status: {result.get('status')}", color="warning"
            #     )
            #     return result, unknown_component

        return {}, html.Div()

    return layout
