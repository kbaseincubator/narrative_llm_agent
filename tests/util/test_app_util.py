from narrative_llm_agent.util.app import (
    get_processed_app_spec_params,
    process_param_type,
    get_ws_object_refs,
    is_valid_ref,
    is_valid_upa,
    generate_input,
    resolve_ref
)
from narrative_llm_agent.kbase.clients.workspace import Workspace

from tests.test_data.test_data import load_test_data_json
from pathlib import Path
import pytest

@pytest.fixture(scope="module")
def app_spec():
    """
    Loads an app spec for testing. This is the NarrativeTest/test_input_params app spec.
    """
    app_spec_path = Path("app_spec_data") / "test_app_spec.json"
    spec = load_test_data_json(app_spec_path)
    return spec

@pytest.fixture(scope="module")
def expected_app_params():
    """
    Loads the pre-processed app spec params from the NarrativeTest/test_input_params spec.
    """
    expected_params_path = Path("app_spec_data") / "app_spec_processed_params.json"
    params_spec = load_test_data_json(expected_params_path)
    return params_spec

@pytest.fixture(scope="module")
def input_params():
    """
    Loads a sample filled out parameter set using the NarrativeTest/test_input_params app.
    """
    params_path = Path("app_spec_data") / "test_app_spec_inputs.json"
    params = load_test_data_json(params_path)
    return params

def test_get_spec_params(app_spec: dict, expected_app_params: dict):
    params = get_processed_app_spec_params(app_spec)
    assert params
    assert params == expected_app_params

@pytest.mark.parametrize("test_type", ["foo", "text", "textarea", "other"])
def test_process_param_type_simple(test_type: str):
    param = {
        "field_type": test_type,
    }
    assert process_param_type(param) == (test_type, [])

@pytest.mark.parametrize("number_type", ["int", "float"])
def test_process_param_type_number(number_type: str):
    param = {
        "field_type": "text",
        "text_options": {
            "validate_as": number_type,
            f"max_{number_type}": 100,
            f"min_{number_type}": 0
        }
    }
    assert process_param_type(param) == (number_type, [0, 100])

def test_process_param_type_data_object():
    ws_types = ["KBaseGenomes.Genome", "SomeOther.Genome"]
    param = {
        "field_type": "text",
        "text_options": {
            "valid_ws_types": ws_types
        }
    }
    assert process_param_type(param) == ("data_object", ws_types)

def test_process_param_type_dropdown():
    dropdown_opts = [{
        "value": "foo",
        "display": "Foo"
    }, {
        "value": "bar",
        "display": "Bar"
    }]
    param = {
        "field_type": "dropdown",
        "dropdown_options": {
            "options": dropdown_opts
        }
    }
    assert process_param_type(param) == ("dropdown", ["Foo", "Bar"])

def test_get_ws_object_refs(app_spec: dict, input_params: dict):
    expected_refs = set(["1/2/3", "1/3/1", "1/4/1"])
    assert set(get_ws_object_refs(app_spec, input_params)) == expected_refs

valid_upas = ["1/2/3", "11/22/33"]
invalid_upas = ["1/2", "1/2/3/4", None, 1, "nope"]
@pytest.mark.parametrize(
    "test_str,expected",
    [(good, True) for good in valid_upas] +
    [(bad, False) for bad in invalid_upas]
)
def test_is_valid_upa(test_str: str, expected: bool):
    assert is_valid_upa(test_str) == expected

valid_refs = valid_upas + ["some/ref", "1/2"]
invalid_refs = invalid_upas[1:]
@pytest.mark.parametrize(
    "test_str,expected",
    [(good, True) for good in valid_refs] +
    [(bad, False) for bad in invalid_refs]
)
def test_is_valid_ref(test_str: str, expected: bool):
    assert is_valid_ref(test_str) == expected

def test_generate_input():
    prefix = "pre"
    suffix = "suf"
    num_symbols = 8
    generator = {"symbols": num_symbols, "prefix": prefix, "suffix": suffix}
    rand_str = generate_input(generator)
    assert rand_str.startswith(prefix)
    assert rand_str.endswith(suffix)
    assert len(rand_str) == len(prefix) + len(suffix) + num_symbols

def test_generate_input_default():
    rand_str = generate_input()
    assert len(rand_str) == 8

def test_generate_input_bad():
    with pytest.raises(ValueError):
        generate_input({"symbols": "foo"})
    with pytest.raises(ValueError):
        generate_input({"symbols": -1})

def test_resolve_ref(mock_workspace):
    ws_id = 1000
    upa = "1000/2/3"
    assert resolve_ref(ws_id, upa, mock_workspace) == upa

def test_resolve_ref_list(mock_workspace):
    ws_id = 1000
    ref_list = ["1000/2", "1000/bar"]
    assert resolve_ref(ws_id, ref_list, mock_workspace) == ["1000/2/3", "1000/3/4"]
