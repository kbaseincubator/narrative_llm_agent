import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, callback, callback_context
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
        Output(CREDENTIALS_STORE, "data", allow_duplicate=True),
        Output(CREDENTIALS_LOCAL_STORE, "data"),
        Output(auth_id, "value"),
        Output(provider_id, "value"),
        Output(api_key_id, "value"),
        Output(store_id, "value"),
        Output("credentials-label", "children"),
        Output(message_id, "is_open", allow_duplicate=True),
        Output(message_id, "color", allow_duplicate=True),
        Output(message_id, "children", allow_duplicate=True),
        Output(message_id, "duration", allow_duplicate=True),
    ],
    [
        Input(btn_id, "n_clicks"),
        Input(CREDENTIALS_LOCAL_STORE, "modified_timestamp"),
    ],
    [
        State(store_id, "value"),
        State(provider_id, "value"),
        State(auth_id, "value"),
        State(api_key_id, "value"),
        State(CREDENTIALS_LOCAL_STORE, "data"),
        State(CREDENTIALS_STORE, "data"),
    ],
    prevent_initial_call=True,
)
def handle_credentials(cred_clicks, timestamp, store_local, provider, kb_auth_token, api_key, local_creds, current_creds):
    """
    Handles credential validation and storage for both button clicks and page load.
    Validates credentials only once and stores them appropriately.
    """
    ctx = callback_context

    # Default return values for form fields and labels
    default_return = (
        {},  # CREDENTIALS_STORE
        {},  # CREDENTIALS_LOCAL_STORE
        None,  # auth_id value
        default_provider,  # provider_id value
        None,  # api_key_id value
        False,  # store_id value
        "",  # credentials-label
        False,  # message is_open
        "",  # message color
        "",  # message children
        SUCCESS_MSG_DURATION  # message duration
    )

    # Determine trigger source
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    if triggered_id == btn_id:
        # Button was clicked - validate form inputs
        if not cred_clicks:
            return default_return

        # Use form values for validation
        validation_provider = provider
        validation_auth_token = kb_auth_token
        validation_api_key = api_key
        should_store_local = store_local

    elif triggered_id == CREDENTIALS_LOCAL_STORE:
        # Local storage was updated - check if we need to load from it
        if current_creds:
            # Credentials already exist, just update form with current values
            provider = current_creds["provider"]
            api_key = current_creds["cborg_api_key"] if provider == "cborg" else current_creds["openai_api_key"]
            return (
                current_creds,  # CREDENTIALS_STORE
                local_creds or {},  # CREDENTIALS_LOCAL_STORE
                current_creds["kb_auth_token"],  # auth_id value
                provider,  # provider_id value
                api_key,  # api_key_id value
                True,  # store_id value
                make_loaded_message(current_creds["kb_user_id"], current_creds["kb_user_display"], current_creds["provider"]),
                False,  # message is_open
                "",  # message color
                "",  # message children
                SUCCESS_MSG_DURATION  # message duration
            )

        if not local_creds:
            # No local credentials to load
            return default_return

        # Use local storage values for validation
        validation_provider = local_creds.get(provider_id)
        validation_auth_token = local_creds.get(auth_id)
        validation_api_key = local_creds.get(api_key_id)
        should_store_local = True  # Already stored locally

    else:
        return default_return

    # Validate credentials (this happens only once per trigger)
    user_info, errors = validate_credentials(validation_auth_token, validation_provider, validation_api_key)

    if errors:
        # Validation failed
        return (
            {},  # CREDENTIALS_STORE (keep empty)
            {} if triggered_id == btn_id else local_creds,  # CREDENTIALS_LOCAL_STORE
            validation_auth_token if triggered_id == CREDENTIALS_LOCAL_STORE else None,
            validation_provider if triggered_id == CREDENTIALS_LOCAL_STORE else default_provider,
            validation_api_key if triggered_id == CREDENTIALS_LOCAL_STORE else None,
            should_store_local if triggered_id == CREDENTIALS_LOCAL_STORE else False,
            "" if triggered_id == btn_id else "",
            True,  # message is_open
            "danger",  # message color
            ", ".join(errors),  # message children
            FAIL_MSG_DURATION  # message duration
        )

    # Validation successful - create credentials object
    credentials = {
        "provider": validation_provider,
        "kb_user_id": user_info["user_name"],
        "kb_user_display": user_info["display_name"],
        "kb_auth_token": validation_auth_token,
        "neo4j_uri": os.environ.get("NEO4J_URI", ""),
        "neo4j_username": os.environ.get("NEO4J_USERNAME", ""),
        "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
    }

    if validation_provider == "cborg":
        credentials["cborg_api_key"] = validation_api_key
    else:
        credentials["openai_api_key"] = validation_api_key

    # Determine browser storage
    if should_store_local:
        browser_store = {
            auth_id: validation_auth_token,
            provider_id: validation_provider,
            api_key_id: validation_api_key,
            "kb_user_id": credentials["kb_user_id"],
            "kb_user_display": credentials["kb_user_display"]
        }
    else:
        browser_store = {}

    # Create success message
    if triggered_id == btn_id:
        success_message = "Credentials validated and saved!"
    else:
        success_message = "Successfully loaded credentials"

    return (
        credentials,  # CREDENTIALS_STORE
        browser_store,  # CREDENTIALS_LOCAL_STORE
        validation_auth_token,  # auth_id value
        validation_provider,  # provider_id value
        validation_api_key,  # api_key_id value
        should_store_local,  # store_id value
        make_loaded_message(credentials["kb_user_id"], credentials["kb_user_display"], credentials["provider"]) if triggered_id == CREDENTIALS_LOCAL_STORE else "",
        True,  # message is_open
        "success",  # message color
        success_message,  # message children
        SUCCESS_MSG_DURATION  # message duration
    )


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
