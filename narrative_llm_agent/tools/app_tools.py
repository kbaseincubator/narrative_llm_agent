from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, create_model
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.objects.app_spec import AppParameter, AppSpec
from narrative_llm_agent.util.app import get_processed_app_spec_params


def get_app_params(app_id: str, nms: NarrativeMethodStore) -> dict:
    spec = nms.get_app_spec(app_id, include_full_info=True)
    return get_processed_app_spec_params(AppSpec(**spec))


def app_params_pydantic(app_spec: AppSpec) -> BaseModel:
    model_atts = {}
    proc = get_processed_app_spec_params(app_spec)
    params_dict = {}
    for param in app_spec.parameters:
        params_dict[param.id] = param
    # the individual parameters that are part of a group.
    param_group_params = set()
    param_group_model_atts = {}
    if app_spec.parameter_groups is not None:
        for param_group in app_spec.parameter_groups:
            param_group_params.update(param_group.parameter_ids)
            group_model_atts = {}
            for param_id in param_group.parameter_ids:
                group_model_atts[param_id] = _param_to_model_attribute(
                    params_dict[param_id],
                    proc[param_group.id]["params"][param_id]["type"]
                )
            pg_model = create_model(
                f"{param_group.id}Model",
                **group_model_atts,
                __config__=ConfigDict(regex_engine="python-re")
            )
            if param_group.allow_multiple == 1:
                param_group_model_atts[param_group.id] = list[pg_model]
            else:
                param_group_model_atts[param_group.id] = pg_model
            if param_group.optional == 1:
                param_group_model_atts[param_group.id] = (param_group_model_atts[param_group.id], None)

    for param in app_spec.parameters:
        if param.id not in param_group_params:
            model_atts[param.id] = _param_to_model_attribute(param, proc[param.id].get("type", "string"))

    model_atts = model_atts | param_group_model_atts
    return create_model(
        "AppParamsModel",
        **model_atts,
        __config__=ConfigDict(regex_engine="python-re")
    )

def _param_to_model_attribute(param: AppParameter, param_type: str):
    """
    `param_type` is figured out from the processed version - turns "text" into "data_object",
    for example.
    """
    param_attr = str   # default
    if param.default_values is not None and len(param.default_values):
        default_value = param.default_values[0]
    else:
        default_value = None
    # lots of cases here...
    if param_type == "int":
        param_attr = Annotated[
            int,
            Field(
                strict=True,
                ge=param.text_options.min_int,
                le=param.text_options.max_int
            )
        ]
        try:
            default_value = int(default_value)
        except Exception:
            default_value = 0
    if param_type == "float":
        param_attr = Annotated[
            float,
            Field(
                strict=True,
                ge=param.text_options.min_float,
                le=param.text_options.max_float
            )
        ]
        try:
            default_value = float(default_value)
        except Exception:
            default_value = 0.0
    elif param_type == "dropdown":
        if param.dropdown_options is None:
            param_attr = Literal[None]
        else:
            param_attr = Literal[
                *[opt.value for opt in param.dropdown_options.options]
            ]
    elif param_type == "checkbox":
        param_attr, default_value = _pydantic_checkbox(param, default_value)
    elif param_type == "data_object" and param.text_options.is_output_name == 1:
        # from the workspace docs:
        # the object name must be alphanumeric, and can have _\.- characters, and NOT be
        # only numeric.
        param_attr = Annotated[
            str,
            Field(
                strict=True,
                pattern=r"^(?!\d+$)[A-Za-z0-9|_\.-]+$"
            )
        ]
    if param.allow_multiple == 1:
        param_attr = list[param_attr]

    if param.optional == 1:
        return (param_attr, default_value)
    return param_attr


def _pydantic_checkbox(param: AppParameter, default_value: str):
    """
    TODO: figure out how to do typing for the return. Apparently, just a bare Literal doesn't work.
    """
    param_attr = Literal[
        param.checkbox_options.checked_value,
        param.checkbox_options.unchecked_value
    ]
    # This is very silly, but for checkboxes, the values must be integers,
    # and all default values are always strings.
    # some of these strings, instead of matching the checkbox values, are "false" or "true"
    # or "False" or "0" or "1" or whatever.
    # We turn the default into either the checked or unchecked value here.
    # If the default is either "1" or "true" (or "True"), it becomes the checked value.
    # all other cases become unchecked.
    # If it's an empty string, set it to the unchecked value.
    new_default = param.checkbox_options.unchecked_value
    if default_value.lower().strip() in ["1", "true"]:
        new_default = param.checkbox_options.checked_value
    return param_attr, new_default
