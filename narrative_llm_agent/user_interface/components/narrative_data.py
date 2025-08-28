
from typing import List
from dash import dcc, Input, Output, State, callback, html
import dash_bootstrap_components as dbc

from narrative_llm_agent.kbase.clients.search import NarrativeDoc, Search
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.user_interface.constants import CREDENTIALS_STORE, DATA_SELECTION_STORE, METADATA_STORE

NARRATIVE_SEL = "narrative-select"
OBJECT_SEL = "object-select"
START_BTN = "start-with-data-btn"

def narrative_data_dropdown():
    return dbc.Card([
        dbc.CardHeader("Select data for analysis"),
        dbc.CardBody([
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H5("Narrative"),
                            dcc.Dropdown(
                                id=NARRATIVE_SEL,
                            )
                        ]
                    ),
                    dbc.Col(
                        [
                            html.H5("Object"),
                            dcc.Dropdown(
                                id=OBJECT_SEL
                            )
                        ]
                    ),
                ],
                class_name="mb-3"
            ),
            dbc.Row(
                dbc.Col(
                    dbc.Button(
                        "Start Analysis", id=START_BTN, color="success", disabled=True
                    ),
                    width=2
                )
            )
        ]),
    ], class_name="mb-2")

@callback(
    Output(NARRATIVE_SEL, "options"),
    Input(CREDENTIALS_STORE, "modified_timestamp"),
    State(CREDENTIALS_STORE, "data"),
    prevent_initial_call=True
)
def init_narrative_dropdown(_, creds):
    print("initing narratives")
    if not creds.get("kb_user_id"):
        return []
    narratives = lookup_narratives(creds["kb_user_id"], creds["kb_auth_token"])
    return [{"label": narr.narrative_title, "value": narr.access_group} for narr in narratives]


@callback(
    Output(OBJECT_SEL, "options"),
    Input(NARRATIVE_SEL, "value"),
    State(CREDENTIALS_STORE, "data"),
    prevent_initial_call=True
)
def init_object_dropdown(narrative_id, creds):
    print(f"initing objects - narrative_id {narrative_id}")
    if not narrative_id:
        return []
    objs = sorted(lookup_objects(narrative_id, creds["kb_auth_token"]), key=lambda x: x["type"])
    return [{
        "label": f"{obj['name']} - {obj['type'].split('-')[0].split('.')[-1]}",
        "value": obj["upa"]
    } for obj in objs]

@callback(
    Output(METADATA_STORE, "data", allow_duplicate=True),
    Output(DATA_SELECTION_STORE, "data"),
    Output(START_BTN, "disabled"),
    Input(NARRATIVE_SEL, "value"),
    Input(OBJECT_SEL, "value"),
    State(CREDENTIALS_STORE, "data"),
    prevent_initial_call=True
)
def set_narr_and_upa(narrative_id, obj_upa, creds):
    if narrative_id is not None and obj_upa is not None:
        ws = Workspace(token=creds["kb_auth_token"])
        obj_info = ws.get_object_info(obj_upa)
        data = {"narrative_id": narrative_id, "obj_upa": obj_upa, "obj_metadata": obj_info.metadata}
        return data, data, False
    return {}, {}, True

def lookup_narratives(user_id: str, auth_token: str) -> List[NarrativeDoc]:
    try:
        search = Search(token=auth_token)
        results = search.search_narratives(user_id)
        return results.hits
    except Exception as e:
        raise e

def lookup_objects(narrative_id: int, auth_token: str) -> List[dict[str, str]]:
    ws = Workspace(token=auth_token)
    objs = ws.list_workspace_objects(narrative_id, as_dict=True)
    # filter out narratives and reports
    return list(filter(lambda x: not x["type"].startswith("KBaseNarrative.Narrative"), objs))
