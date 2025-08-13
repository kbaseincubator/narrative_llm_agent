import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, callback
import os
from narrative_llm_agent.kbase.clients.auth import KBaseAuth
from narrative_llm_agent.kbase.clients.cborg import CborgAuth
from narrative_llm_agent.kbase.clients.openai import OpenAIAuth
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE

SUCCESS_MSG_DURATION = 5000
FAIL_MSG_DURATION = 500000

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
                                    className="mt-3 mb-0",
                                    color="primary"
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
        [
            Output(CREDENTIALS_STORE, "data"),
            Output(message_id, "is_open"),
            Output(message_id, "color"),
            Output(message_id, "children"),
            Output(message_id, "duration"),
        ],
        Input(btn_id, "n_clicks"),
        [
            State(provider_id, "value"),
            State(auth_id, "value"),
            State(api_key_id, "value"),
        ],
        prevent_initial_call=True,
    )
    def save_credentials(n_clicks, provider, kb_auth_token, api_key):
        """
        TODO: validate kbase auth token, api key
        This saves a new set of credentials.
        It removes all keys and re-stores them.
        This only stores user credentials. NEO4J ones should not be set by the user,
        and are only available as environment vars by the app.
        """
        if not n_clicks:
            return {}, False, "", "", SUCCESS_MSG_DURATION

        kbase_auth = KBaseAuth()
        try:
            user_info = kbase_auth.get_user_display_name(kb_auth_token)
        except Exception as err:
            return {}, True, "danger", f"KBase token error: {str(err)}", FAIL_MSG_DURATION

        if provider == "cborg":
            llm_key_client = CborgAuth()
        elif provider == "openai":
            llm_key_client = OpenAIAuth()
        else:
            return {}, False, "danger", f"Unknown LLM provider {provider}", FAIL_MSG_DURATION

        try:
            llm_key_client.validate_key(api_key)
        except Exception as err:
            return {}, True, "danger", f"{provider} API key error: {str(err)}", FAIL_MSG_DURATION

        credentials = {
            "provider": provider,
            "kb_user_id": user_info["user_name"],
            "kb_user_display": user_info["display_name"],
            "kb_auth_token": kb_auth_token or "",
            "neo4j_uri": os.environ.get("NEO4J_URI", ""),
            "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
            "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
        }

        if provider == "cborg":
            credentials["cborg_api_key"] = api_key
        else:
            credentials["openai_api_key"] = api_key

        return credentials, True, "success", "Credentials validated and saved!", SUCCESS_MSG_DURATION

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
