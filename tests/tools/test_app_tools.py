from pathlib import Path

from pytest_mock import MockerFixture

from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.tools.app_tools import get_app_params
from tests.test_data.test_data import load_test_data_json


def test_get_app_params_tool(app_spec: AppSpec, mocker: MockerFixture):
    mock_nms = mocker.Mock(spec=NarrativeMethodStore)
    mock_nms.get_app_spec.return_value = app_spec.model_dump()
    expected_params_path = Path("app_spec_data") / "app_spec_processed_params.json"
    params_spec = load_test_data_json(expected_params_path)
    assert get_app_params("some_app_id", mock_nms) == params_spec
