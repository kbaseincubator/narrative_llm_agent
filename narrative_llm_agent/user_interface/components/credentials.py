import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, callback
import os
from narrative_llm_agent.kbase.clients.auth import KBaseAuth
from narrative_llm_agent.kbase.clients.cborg import CborgAuth
from narrative_llm_agent.kbase.clients.openai import OpenAIAuth
from narrative_llm_agent.user_interface.constants import CREDENTIALS_LOCAL_STORE, CREDENTIALS_STORE

SUCCESS_MSG_DURATION = 5000
FAIL_MSG_DURATION = 500000

provider_id = "provider-dropdown"
auth_id = "kb-auth-token"
api_key_id = "api-key"
api_key_label_id = "api-key-label"
btn_id = "save-credentials-btn"
message_id = "save-credentials-msg"
store_id = "store-credentials"
default_provider = "openai"

def create_credentials_form() -> dbc.Accordion:
    """
    This should only be invoked once. Duplicates will make bad things happen.
    To make a duplicate, this should be modified to make unique ids
    """

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
                                        value=default_provider,
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
                                [
                                    dbc.Switch(
                                        id=store_id,
                                        label="Store credentials in browser",
                                        value=False
                                    )
                                ]
                            )
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Save Credentials", id=btn_id, className="py-2", color="primary"
                                ),
                                width=2
                            ),
                            dbc.Col(
                                html.Div(
                                    dbc.Spinner(
                                        dbc.Alert(
                                            "",
                                            id=message_id,
                                            is_open=False,
                                            duration=5000,
                                            dismissable=True,
                                            className="mt-0 mb-0 py-2",
                                            color="primary",
                                        ),
                                    )
                                )
                            )
                        ]
                    ),
                ],
                title = html.Div([
                    html.Div("🔑 KBase Credentials"),
                    html.Div("", id="credentials-label", style={"marginLeft": "1rem"})
                ], className="d-flex  justify-content-end")
            ),
        ]
    )
    return layout


# Callback for saving credentials
@callback(
    [
        Output(CREDENTIALS_STORE, "data", allow_duplicate=True),
        Output(CREDENTIALS_LOCAL_STORE, "data"),
        Output(message_id, "is_open"),
        Output(message_id, "color"),
        Output(message_id, "children", allow_duplicate=True),
        Output(message_id, "duration"),
    ],
    [
        Input(btn_id, "n_clicks"),
    ],
    [
        State(store_id, "value"),
        State(provider_id, "value"),
        State(auth_id, "value"),
        State(api_key_id, "value"),
        State(CREDENTIALS_LOCAL_STORE, "data")
    ],
    prevent_initial_call=True,
)
def save_credentials(cred_clicks, store_local, provider, kb_auth_token, api_key, current_browser_store):
    """
    This saves a new set of credentials.
    It removes all keys and re-stores them.
    This only stores user credentials. NEO4J ones should not be set by the user,
    and are only available as environment vars by the app.
    """
    if not cred_clicks:
        return {}, current_browser_store, False, "", "", SUCCESS_MSG_DURATION

    user_info, errors = validate_credentials(kb_auth_token, provider, api_key)

    if errors:
        return {}, current_browser_store, True, "danger", ", ".join(errors), FAIL_MSG_DURATION

    credentials = {
        "provider": provider,
        "kb_user_id": user_info["user_name"],
        "kb_user_display": user_info["display_name"],
        "kb_auth_token": kb_auth_token,
        "neo4j_uri": os.environ.get("NEO4J_URI", ""),
        "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
        "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
    }

    if store_local:
        browser_store = {
            auth_id: kb_auth_token,
            provider_id: provider,
            api_key_id: api_key,
            "kb_user_id": credentials["kb_user_id"],
            "kb_user_display": credentials["kb_user_display"]
        }
    else:
        browser_store = {}

    if provider == "cborg":
        credentials["cborg_api_key"] = api_key
    else:
        credentials["openai_api_key"] = api_key

    return credentials, browser_store, True, "success", "Credentials validated and saved!", SUCCESS_MSG_DURATION

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

@callback(
    [
        Output(CREDENTIALS_STORE, "data"),
        Output(auth_id, "value"),
        Output(provider_id, "value"),
        Output(api_key_id, "value"),
        Output(store_id, "value"),
        Output("credentials-label", "children"),
    ],
    Input(CREDENTIALS_LOCAL_STORE, "modified_timestamp"),
    [
        State(CREDENTIALS_LOCAL_STORE, "data"),
        State(CREDENTIALS_STORE, "data")
    ]
)
def initialize_from_store(_, local_creds, creds):
    """
    This function triggers when the store timestamp is updated. Which is (AFACT) twice:
    1. On page load if local storage exists
    2. When the local storage is saved, so when the user hits the save button.
    In the second case, we don't need to do anything, so just return the creds as they are.
    Otherwise, load them from storage, validate them, then return.
    """
    if creds:
        provider = creds["provider"]
        api_key = creds["cborg_api_key"] if provider == "cborg" else creds["openai_api_key"]
        return creds, creds["kb_auth_token"], provider, api_key, True, make_loaded_message(creds["kb_user_id"], creds["kb_user_display"], creds["provider"])
    if not local_creds:
        return {}, None, default_provider, None, False, ""

    provider = local_creds.get(provider_id)
    api_key = local_creds.get(api_key_id)
    user_info, errors = validate_credentials(local_creds[auth_id], provider, api_key)
    if len(errors):
        return {}, None, default_provider, None, False, ""

    loaded_credentials = {
        "provider": provider,
        "kb_user_id": user_info.get("user_name", ""),
        "kb_user_display": user_info.get("display_name", ""),
        "kb_auth_token": local_creds.get(auth_id),
        "neo4j_uri": os.environ.get("NEO4J_URI", ""),
        "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
        "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
    }

    if loaded_credentials["provider"] == "cborg":
        loaded_credentials["cborg_api_key"] = api_key
    else:
        loaded_credentials["openai_api_key"] = api_key

    return loaded_credentials, loaded_credentials["kb_auth_token"], provider, api_key, True, make_loaded_message(loaded_credentials["kb_user_id"], loaded_credentials["kb_user_display"], loaded_credentials["provider"])


def validate_credentials(kbase_token: str, llm_provider: str, llm_key: str):
    errors = []
    kbase_auth = KBaseAuth()
    user_info = None
    try:
        user_info = kbase_auth.get_user_display_name(kbase_token)
    except Exception as err:
        errors.append(f"KBase token error: {str(err)}")

    llm_key_client = None
    if llm_provider == "cborg":
        llm_key_client = CborgAuth()
    elif llm_provider == "openai":
        llm_key_client = OpenAIAuth()
    else:
        errors.append(f"Unknown LLM provider {llm_provider}")

    if llm_key_client is not None:
        try:
            llm_key_client.validate_key(llm_key)
        except Exception as err:
            errors.append(f"{llm_provider} API key error: {str(err)}")
    return user_info, errors

def make_loaded_message(user_id: str, user_name: str, provider: str):
    if provider == "cborg":
        provider = "CBORG"
    elif provider == "openai":
        provider = "OpenAI"
    return f"Welcome KBase user {user_name} ({user_id}), using {provider} LLMs"
