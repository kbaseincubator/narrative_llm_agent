import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, callback
import os
from narrative_llm_agent.kbase.clients.auth import KBaseAuth
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE

def create_credentials_form() -> dbc.Accordion:
    """
    This should only be invoked once. Duplicates will make bad things happen.
    To make a duplicate, this should be modified to make unique ids
    """
    provider_id = "provider-dropdown"
    auth_id = "kb-auth-token"
    api_key_id = "api-key"
    api_key_label_id = "api-key-label"
    btn_id = "save-credentials-btn"
    message_id = "save-credentials-msg"

    layout = dbc.Accordion(
        [
            dbc.AccordionItem(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("LLM Provider"),
                                    dcc.Dropdown(
                                        id=provider_id,
                                        options=[
                                            {"label": "OpenAI", "value": "openai"},
                                            {"label": "CBORG (LBL)", "value": "cborg"},
                                        ],
                                        value="openai",
                                    ),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("API Key", id=api_key_label_id),
                                    dbc.Input(
                                        id=api_key_id,
                                        type="password",
                                        placeholder="Enter your API key",
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
                                    dbc.Label("KBase Auth Token"),
                                    dbc.Input(
                                        id=auth_id,
                                        type="password",
                                        placeholder="Enter your KBase authentication token",
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
                                dbc.Button(
                                    "Save Credentials", id=btn_id, color="primary"
                                ),
                                width=2
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Alert(
                                    "",
                                    id=message_id,
                                    is_open=False,
                                    duration=5000,
                                    dismissable=True,
                                    className="mt-3 mb-0"
                                ),
                                width="auto",
                            )
                        ],
                    )
                ],
                title = "🔑 KBase Credentials"
            ),
        ]
    )

    # Callback for saving credentials
    @callback(
        Output(CREDENTIALS_STORE, "data"),
        Output(message_id, "is_open"),
        Output(message_id, "children"),
        Input(btn_id, "n_clicks"),
        State(provider_id, "value"),
        State(auth_id, "value"),
        State(api_key_id, "value"),
        prevent_initial_call=True,
    )
    def save_credentials(n_clicks, provider, kb_auth_token, api_key):
        """
        TODO: validate kbase auth token, api key
        """
        if n_clicks:
            credentials = {
                "provider": provider,
                "kb_auth_token": kb_auth_token or "",
                "neo4j_uri": os.environ.get("NEO4J_URI", ""),
                "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
                "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
            }

            if provider == "cborg":
                credentials["cborg_api_key"] = api_key or ""
            else:
                credentials["openai_api_key"] = api_key or ""

            return credentials, True, "Credentials saved!"
        return {}, False, ""

    @callback(
        Output(api_key_label_id, "children"),
        Output(api_key_id, "placeholder"),
        Input(provider_id, "value")
    )
    def toggle_api_title(provider):
        if provider == "openai":
            return "OpenAI API Key", "Enter your OpenAI API key"
        else:
            return "CBORG API Key", "Enter your CBORG API key"

    return layout
