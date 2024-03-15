def get_processed_app_spec_params(app_spec: dict) -> dict:
    """
    This processes the given KBase app spec and returns the
    parameter structure out of it in a way that a fairly dim LLM
    can populate it. Hopefully.
    TODO: build an AppSpec class that maintains the structure. But, YAGNI.
    """
    used_keys = ["id", "ui_name", "short_hint"]
    processed_params = []
    for param in app_spec["parameters"]:
        proc_param = { key: param[key] for key in used_keys }
        param_type, allowed_values = process_param_type(param)
        proc_param["type"] = param_type
        proc_param["allowed"] = allowed_values
        if "default_values" in param:
            defaults = param["default_values"]
            if param["allow_multiple"] == 1:
                proc_param["default_value"] = defaults
            if len(defaults) and len(defaults[0]):
                proc_param["default_value"] = defaults[0]
            else:
                proc_param["default_value"] = None
        processed_params.append(proc_param)
    return processed_params

def process_param_type(param: dict) -> tuple:
    """
    Processes the type of parameter this is.
    Expands on the KBase typespec to include "data_object" and others
    """
    field_type = param["field_type"]
    allowed_values = []
    # allowed field_type values text | textarea | textsubdata | intslider |
    # floatslider | checkbox | dropdown | radio | tab | file | dynamic_dropdown
    if field_type == "text" and "text_options" in param:
        opts = param["text_options"]
        if "valid_ws_types" in opts:
            field_type = "data_object"
            allowed_values = opts["valid_ws_types"]
        elif "validate_as" in opts and opts["validate_as"] is not None:
            valid_type = opts["validate_as"]
            field_type = valid_type
            allowed_values = [opts.get(f"min_{valid_type}"), opts.get(f"max_{valid_type}")]
    if field_type == "dropdown" and "dropdown_options" in param:
        allowed_values = [opt["display"] for opt in param["dropdown_options"].get("options", [])]
    # TODO types-
    # textsubdata
    # dynamic_dropdown
    # these both depend on external data sources.
    # not exactly necessary to start with, I don't think.
    return (field_type, allowed_values)


def process_app_params(app_spec: dict, params: dict) -> dict:
    """
    Processes the given parameters to run the app. This returns
    the validated structure that can be passed along to the Execution
    Engine.
    """
    return {}

def build_run_job_params(app_spec: dict, params: dict, narrative_id: int) -> dict:
    """
    This process the parameters along with the app spec to build the
    packet that gets sent to the Execution Engine's run_job command.
    This also creates a cell_id and run_id and various other required metadata.
    """
    return {}
