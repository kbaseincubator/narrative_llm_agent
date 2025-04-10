from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.util.app import get_processed_app_spec_params


def get_app_params(app_id: str, nms: NarrativeMethodStore) -> dict:
    spec = nms.get_app_spec(app_id, include_full_info=True)
    return get_processed_app_spec_params(AppSpec(**spec))
