from narrative_llm_agent.util.app import (
    get_processed_app_spec_params
)
from tests.test_data.test_data import load_test_data_json
from pathlib import Path
import pytest

@pytest.fixture(scope="module")
def app_spec():
    app_spec_path = Path("app_spec_data") / "test_app_spec.json"
    spec = load_test_data_json(app_spec_path)
    yield spec

@pytest.fixture(scope="module")
def expected_app_params():
    expected_params_path = Path("app_spec_data") / "app_spec_processed_params.json"
    params_spec = load_test_data_json(expected_params_path)
    yield params_spec

def test_get_spec_params(app_spec: dict, expected_app_params: dict):
    params = get_processed_app_spec_params(app_spec)
    assert params
    assert params == expected_app_params

