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
