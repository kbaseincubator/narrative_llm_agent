from pathlib import Path
import pytest

from pytest_mock import MockerFixture

from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.objects.app_spec import (
    AppSpec,
    AppParameter,
    AppParameterGroup,
    AppBriefInfo,
    WidgetSpec,
    AppBehavior,
    TextOptions,
    DropdownOption,
    DropdownOptions,
    CheckboxOptions
)
from narrative_llm_agent.tools.app_tools import (
    get_app_params,
    app_params_pydantic
)
from tests.test_data.test_data import load_test_data_json


def test_get_app_params_tool(app_spec: AppSpec, mocker: MockerFixture):
    mock_nms = mocker.Mock(spec=NarrativeMethodStore)
    mock_nms.get_app_spec.return_value = app_spec.model_dump()
    expected_params_path = Path("app_spec_data") / "app_spec_processed_params.json"
    params_spec = load_test_data_json(expected_params_path)
    assert get_app_params("some_app_id", mock_nms) == params_spec

@pytest.fixture
def base_info():
    return AppBriefInfo(
        id="test.app",
        module_name="TestModule",
        git_commit_hash=None,
        name="Test App",
        ver="1.0.0",
        subtitle="A test app",
        tooltip="This is a test app",
        categories=["test"],
        loading_error=None,
        authors=["test_user"],
        input_types=[],
        output_types=[],
        app_type="app",
        icon=None
    )

@pytest.fixture
def widget_spec():
    return WidgetSpec(input="input", output="output")

@pytest.fixture
def behavior():
    return AppBehavior()

def test_single_required_string_param(base_info, widget_spec, behavior):
    param = AppParameter(
        id="param1",
        ui_name="Param 1",
        short_hint="hint",
        description="desc",
        field_type="text",
        allow_multiple=0,
        optional=0,
        advanced=0,
        disabled=0,
        default_values=[],
        ui_class="input",
        text_options=TextOptions()
    )
    app_spec = AppSpec(
        info=base_info,
        widgets=widget_spec,
        behavior=behavior,
        parameters=[param]
    )
    model_cls = app_params_pydantic(app_spec)
    model = model_cls(param1="value")
    assert model.param1 == "value"

def test_optional_int_with_default(base_info, widget_spec, behavior):
    param = AppParameter(
        id="int_param",
        ui_name="Int Param",
        short_hint="hint",
        description="desc",
        field_type="text",
        allow_multiple=0,
        optional=1,
        advanced=0,
        disabled=0,
        default_values=["5"],
        ui_class="input",
        text_options=TextOptions(validate_as="int", min_int=0, max_int=10)
    )
    app_spec = AppSpec(
        info=base_info,
        widgets=widget_spec,
        behavior=behavior,
        parameters=[param]
    )
    model_cls = app_params_pydantic(app_spec)
    model = model_cls()
    assert model.int_param == 5

def test_checkbox_param(base_info, widget_spec, behavior):
    param = AppParameter(
        id="check",
        ui_name="Checkbox Param",
        short_hint="hint",
        description="desc",
        field_type="checkbox",
        allow_multiple=0,
        optional=0,
        advanced=0,
        disabled=0,
        default_values=["true"],
        ui_class="input",
        checkbox_options=CheckboxOptions(checked_value=1, unchecked_value=0)
    )
    app_spec = AppSpec(
        info=base_info,
        widgets=widget_spec,
        behavior=behavior,
        parameters=[param]
    )
    model_cls = app_params_pydantic(app_spec)
    model = model_cls(check=1)
    assert model.check == 1

def test_dropdown_param(base_info, widget_spec, behavior):
    param = AppParameter(
        id="select",
        ui_name="Dropdown Param",
        short_hint="hint",
        description="desc",
        field_type="dropdown",
        allow_multiple=0,
        optional=0,
        advanced=0,
        disabled=0,
        default_values=["opt1"],
        ui_class="input",
        dropdown_options=DropdownOptions(
            options=[DropdownOption(value="opt1", display="Option 1")]
        )
    )
    app_spec = AppSpec(
        info=base_info,
        widgets=widget_spec,
        behavior=behavior,
        parameters=[param]
    )
    model_cls = app_params_pydantic(app_spec)
    model = model_cls(select="opt1")
    assert model.select == "opt1"

def test_parameter_group_optional_multiple(base_info, widget_spec, behavior):
    param1 = AppParameter(
        id="g1p1",
        ui_name="Group Param 1",
        short_hint="hint",
        description="desc",
        field_type="text",
        allow_multiple=0,
        optional=0,
        advanced=0,
        disabled=0,
        default_values=[],
        ui_class="input",
        text_options=TextOptions()
    )
    param2 = AppParameter(
        id="g1p2",
        ui_name="Group Param 2",
        short_hint="hint",
        description="desc",
        field_type="text",
        allow_multiple=0,
        optional=0,
        advanced=0,
        disabled=0,
        default_values=[],
        ui_class="input",
        text_options=TextOptions()
    )
    group = AppParameterGroup(
        id="group1",
        parameter_ids=["g1p1", "g1p2"],
        ui_name="Group 1",
        short_hint="Group hint",
        description="Group desc",
        allow_multiple=1,
        optional=1,
        advanced=0,
        with_border=1
    )
    app_spec = AppSpec(
        info=base_info,
        widgets=widget_spec,
        behavior=behavior,
        parameters=[param1, param2],
        parameter_groups=[group]
    )
    model_cls = app_params_pydantic(app_spec)
    model = model_cls(group1=[{"g1p1": "A", "g1p2": "B"}])
    assert isinstance(model.group1, list)
    assert model.group1[0].g1p1 == "A"
    assert model.group1[0].g1p2 == "B"
