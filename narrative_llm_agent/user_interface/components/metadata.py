import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, html, dcc

from narrative_llm_agent.user_interface.components.metadata_agent_format import format_agent_response
from narrative_llm_agent.user_interface.components.redis_streaming import get_background_callback_manager, get_celery_app
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE, METADATA_CHAT_STORE, METADATA_STORE
from narrative_llm_agent.user_interface.workflow_runners import initialize_metadata_agent
from narrative_llm_agent.util.metadata_util import check_metadata_completion, generate_description_from_metadata, process_metadata_chat
from langchain_core.messages import AIMessage, HumanMessage
from langchain.load import dumps, loads

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
                        "Assistant: Hello! I'm here to help gather information about your computational biology project.",
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
                            )
                        ]
                    ),
                    dcc.Store(id=METADATA_CHAT_STORE, data=[]),
                    dcc.Store(id=METADATA_STORE, data={}),
                ]
            ),
        ],
        id="metadata-card",
        style={"display": "none"},

    )

# TODO: wire this more logically. right now just takes magic name used
# in the narrative_data component
# Also:
# 1. Start with buttons disabled
# 2. Start with loading spinner running
@callback(
    Output("metadata-card", "style"),
    Output("metadata-submit-btn", "disabled"),
    Output("metadata-clear-btn", "disabled"),
    Output("metadata-start-btn", "disabled"),
    Output("metadata-response-space", "children"),
    Input("start-with-data-btn", "n_clicks"),
    prevent_initial_call=True
)
def turn_on_metadata(n_clicks):
    if n_clicks:
        return {}, False, False, False, None
    return {"display": "none"}, True, True, True, "waiting..."

@callback(
    Output("metadata-response-space", "children", allow_duplicate=True),
    Output(METADATA_CHAT_STORE, "data", allow_duplicate=True),
    Input("start-with-data-btn", "n_clicks"),
    State(METADATA_STORE, "data"),
    State(CREDENTIALS_STORE, "data"),
    prevent_initial_call=True
)
def initial_metadata_agent_call(n_clicks, metadata, creds):
    agent_executor = initialize_metadata_agent(creds)
    initial_query = f"""
I am working with narrative id {metadata['narrative_id']} and object UPA {metadata['obj_upa']}.
This object has the registered metadata dictionary: {metadata.get('obj_metadata')}.

Use this information to advance your goals.

If there is enough information here to form an analysis, check with the user first. The user MUST verify that
they see enough information before you can proceed to the next step. If there is not enough information,
ask the user to help fill in missing information.

Always return the final information that was stored in the narrative at the end of the chat session.
"""
    response = process_metadata_chat(agent_executor, initial_query, [])
    return format_agent_response(response), dumps([HumanMessage(content=initial_query), AIMessage(content=response)])

# Metadata Collection Chat Callback - Updated to use the imported module
@callback(
    [
        Output("metadata-response-space", "children", allow_duplicate=True),
        Output(METADATA_CHAT_STORE, "data"),
        Output("metadata-input", "value"),
        Output("metadata-chat-history", "children"),
        Output("proceed-to-analysis-btn", "disabled"),
        Output(METADATA_STORE, "data", allow_duplicate=True),
    ],
    [
        Input("metadata-submit-btn", "n_clicks"),
        Input("metadata-clear-btn", "n_clicks"),
        Input("metadata-start-btn", "n_clicks"),
    ],
    [
        State("metadata-input", "value"),
        State(METADATA_STORE, "data"),
        State(METADATA_CHAT_STORE, "data"),
        State(CREDENTIALS_STORE, "data"),
    ],
    prevent_initial_call=True,
    background=True,
    manager=get_background_callback_manager(celery_app=get_celery_app())
)
def interact_with_metadata_agent(
    submit_clicks, clear_clicks, start_clicks, user_input, metadata, chat_history, credentials
):
    # Initialize metadata agent
    agent_executor = initialize_metadata_agent(credentials)
    try:
        # Handle clear chat
        if ctx.triggered_id == "metadata-clear-btn":
            return reset_metadata_chat()

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

def reset_metadata_chat():
    return (
        format_agent_response("Assistant: Chat cleared. Ready to start over!"),
        [],
        "",
        [],
        True,
        {},
    )
