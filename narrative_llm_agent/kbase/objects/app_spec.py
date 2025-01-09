from typing import Any
from pydantic import BaseModel


class Icon(BaseModel):
    url: str

class AppBriefInfo(BaseModel):
    id: str
    module_name: str | None = None
    git_commit_hash: str | None = None
    name: str
    ver: str
    subtitle: str
    tooltip: str
    categories: list[str]
    loading_error: str | None = None
    authors: list[str]
    input_types: list[str]
    output_types: list[str]
    app_type: str
    icon: Icon | None = None

    # @classmethod
    # def from_dict(cls: "AppBriefInfo", d: dict[str, Any]) -> "AppBriefInfo":
    #     return cls(
    #         **(d | {"icon": (None if d.get("icon") is None else Icon(**d["icon"]))})
    #     )

class WidgetSpec(BaseModel):
    input: str | None = None
    output: str | None = None

class RegexMatcher(BaseModel):
    regex: str
    error_text: str
    match: int  # bool

class TextOptions(BaseModel):
    valid_ws_types: list[str] | None = None
    validate_as: str | None = None
    is_output_name: int  # bool
    placeholder: str | None = None
    min_int: int | None = None
    max_int: int | None = None
    min_float: float | None = None
    max_float: float | None = None
    regex_constraint: list[RegexMatcher] | None = None

    # @classmethod
    # def from_dict(cls: "TextOptions", d: dict[str, Any]) -> "TextOptions":
    #     return cls(
    #         **(d | {
    #             "regex_constraint": (
    #                 None
    #                 if d.get("regex_constraint") is None
    #                 else [RegexMatcher(**matcher) for matcher in d["regex_constraint"]]
    #             )
    #         })
    #     )

# @dataclass
class TextAreaOptions(BaseModel):
    n_rows: int
    placeholder: str

class IntSliderOptions(BaseModel):
    min: int
    max: int
    step: int

class FloatSliderOptions(BaseModel):
    min: float
    max: float

class CheckboxOptions(BaseModel):
    checked_value: int  # bool
    unchecked_value: int  # bool

class DropdownOption(BaseModel):
    value: str
    display: str

class DropdownOptions(BaseModel):
    options: list[DropdownOption]
    multiselection: int  # bool

    # @classmethod
    # def from_dict(cls: "DropdownOptions", d: dict[str, Any]) -> "DropdownOptions":
    #     return cls(
    #         multiselection=d.get("multiselection", 0),
    #         options=[DropdownOption(**option) for option in d.get("options", [])]
    #     )

class DynamicDropdownOptions(BaseModel):
    data_source: str
    service_function: str | None = None
    service_version: str | None = None
    service_params: Any
    selection_id: str | None = None
    exact_match_on: str | None = None
    description_template: str | None = None
    multiselection: int  # bool
    query_on_empty_input: int  # bool
    result_array_index: int
    path_to_selection_items: list[str] | None = None

class RadioOptions(BaseModel):
    id_order: list[str]
    ids_to_options: dict[str, str]
    ids_to_tooltip: dict[str, str]

class TabOptions(BaseModel):
    tab_id_order: list[str]
    tab_id_to_tab_name: dict[str, str]
    tab_id_to_param_ids: dict[str, list[str]]

class SubdataSelection(BaseModel):
    constant_ref: list[str] | None = None
    parameter_id: str
    subdata_included: list[str]
    path_to_subdata: list[str]
    selection_id: str | None = None
    selection_description: list[str] | None = None
    description_template: str | None = None
    service_function: str | None = None
    service_version: str | None = None

class TextSubdataOptions(BaseModel):
    placeholder: str
    multiselection: int  # bool
    show_src_obj: int  # bool
    allow_custom: int  # bool
    subdata_selection: SubdataSelection

    # @classmethod
    # def from_dict(cls: "TextSubdataOptions", d: dict[str, Any]) -> "TextSubdataOptions":
    #     return cls(
    #         **(d | {"subdata_selection": SubdataSelection(**d.get("subdata_selection", {}))})
    #     )

class AppParameter(BaseModel):
    id: str
    ui_name: str
    short_hint: str
    description: str
    field_type: str
    allow_multiple: int  # bool
    optional: int  # bool
    advanced: int  # bool
    disabled: int  # bool
    default_values: list[str]
    ui_class: str
    valid_file_types: list[str] | None = None

    text_options: TextOptions | None = None
    textarea_options: TextAreaOptions | None = None
    intslider_options: IntSliderOptions | None = None
    floatslider_options: FloatSliderOptions | None = None
    checkbox_options: CheckboxOptions | None = None
    dropdown_options: DropdownOptions | None = None
    dynamic_dropdown_options: DynamicDropdownOptions | None = None
    radio_options: RadioOptions | None = None
    tab_options: TabOptions | None = None
    textsubdata_options: TextSubdataOptions | None = None

    # @classmethod
    # def from_dict(cls: "AppParameter", d: dict[str, Any]) -> "AppParameter":
    #     d_modified = deepcopy(d)
    #     simple_subclasses = {
    #         "textarea_options": TextAreaOptions,
    #         "intslider_options": IntSliderOptions,
    #         "floatslider_options": FloatSliderOptions,
    #         "checkbox_options": CheckboxOptions,
    #         "dynamic_dropdown_options": DynamicDropdownOptions,
    #         "radio_options": RadioOptions,
    #         "tab_options": TabOptions
    #     }
    #     complex_subclasses = {
    #         "text_options": TextOptions,
    #         "dropdown_options": DropdownOptions,
    #         "textsubdata_options": TextSubdataOptions
    #     }
    #     for name, option_class in simple_subclasses.items():
    #         if name in d_modified:
    #             d_modified[name] = option_class(**d_modified[name])

    #     for name, option_class in complex_subclasses.items():
    #         if name in d_modified:
    #             d_modified[name] = option_class.from_dict(d_modified[name])
    #     return cls(**d_modified)


class FixedAppParameter(BaseModel):
    ui_name: str
    description: str

class AppParameterGroup(BaseModel):
    id: str
    parameter_ids: list[str]
    ui_name: str
    short_hint: str
    description: str
    allow_multiple: int  # bool
    optional: int  # bool
    advanced: int  # bool
    with_border: int  # bool
    id_mapping: dict[str, str] | None = None

class AutoGeneratedValue(BaseModel):
    prefix: str | None = None
    symbols: int | None = None
    suffix: str | None = None

class ServiceInputMapping(BaseModel):
    input_parameter: str | None = None
    constant_value: Any | None = None
    narrative_system_variable: str | None = None
    generated_value: AutoGeneratedValue | None = None
    target_argument_position: int | None = None
    target_property: str | None = None
    target_type_transform: str | None = None

    # @classmethod
    # def from_dict(cls: "ServiceInputMapping", d: dict[str, Any]) -> "ServiceInputMapping":
    #     return cls(
    #         **(d | {"generated_value": (
    #             None
    #             if "generated_value" not in d
    #             else AutoGeneratedValue(**d["generated_value"])
    #         )})
    #     )

class ServiceOutputMapping(BaseModel):
    input_parameter: str | None = None
    service_method_output_path: list[str] | None = None
    constant_value: Any | None = None
    narrative_system_variable: str | None = None
    target_property: str | None = None
    target_type_transform: str | None = None

class OutputMapping(BaseModel):
    input_parameter: str | None = None
    constant_value: Any | None = None
    narrative_system_variable: str | None = None
    target_property: str | None = None
    target_type_transform: str | None = None

class AppBehavior(BaseModel):
    kb_service_url: str | None = None
    kb_service_name: str | None = None
    kb_service_version: str | None = None
    kb_service_method: str | None = None
    resource_estimator_module: str | None = None
    resource_estimator_method: str | None = None
    kb_service_input_mapping: list[ServiceInputMapping] | None = None
    kb_service_output_mapping: list[ServiceOutputMapping] | None = None
    output_mapping: list[OutputMapping] | None = None

    # @classmethod
    # def from_dict(cls: "AppBehavior", d: dict[str, Any]) -> "AppBehavior":
    #     return cls(
    #         **(
    #             d
    #             | {
    #                 "kb_service_input_mapping": (
    #                     None
    #                     if d.get("kb_service_input_mapping") is None
    #                     else [
    #                         ServiceInputMapping(**mapping)
    #                         for mapping in d["kb_service_input_mapping"]
    #                     ]
    #                 ),
    #                 "kb_service_output_mapping": (
    #                     None
    #                     if d.get("kb_service_output_mapping") is None
    #                     else [
    #                         ServiceOutputMapping(**mapping)
    #                         for mapping in d["kb_service_output_mapping"]
    #                     ]
    #                 ),
    #                 # If output_mapping might be missing, default to empty list
    #                 "output_mapping": [OutputMapping(**mapping) for mapping in d.get("output_mapping", [])],
    #             }
    #         )
    #     )

class AppSpec(BaseModel):
    info: AppBriefInfo
    widgets: WidgetSpec
    parameters: list[AppParameter] | None = None
    fixed_parameters: list[FixedAppParameter] | None = None
    parameter_groups: list[AppParameterGroup] | None = None
    behavior: AppBehavior
    job_id_output_field: str | None = None
    replacement_text: str | None = None

    # @classmethod
    # def from_dict(cls: "AppSpec", d: dict[str: Any]) -> "AppSpec":
    #     parameters = None
    #     if "parameters" in d and d["parameters"] is not None:
    #         parameters = [AppParameter.from_dict(param) for param in d["parameters"]]
    #     fixed_parameters = None
    #     if "fixed_parameters" in d and d["fixed_parameters"] is not None:
    #         fixed_parameters = [FixedAppParameter(**param) for param in d["fixed_parameters"]]
    #     parameter_groups = None
    #     if "parameter_groups" in d and d["parameter_groups"] is not None:
    #         parameter_groups = [AppParameterGroup(**param) for param in d["parameter_groups"]]

    #     return cls(
    #         info=AppBriefInfo.from_dict(d.get("info")),
    #         widgets=WidgetSpec(**d.get("widgets", {})),
    #         parameters=parameters,
    #         fixed_parameters=fixed_parameters,
    #         parameter_groups=parameter_groups,
    #         behavior=AppBehavior.from_dict(d["behavior"]) if "behavior" in d else None,
    #         job_id_output_field=d.get("job_id_output_field")
    #     )
