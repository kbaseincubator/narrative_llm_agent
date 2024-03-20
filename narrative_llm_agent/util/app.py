from typing import Any, Optional
import uuid
import time
import random
import re
from narrative_llm_agent.kbase.clients.workspace import Workspace

def get_processed_app_spec_params(app_spec: dict) -> dict:
    """
    This processes the given KBase app spec and returns the
    parameter structure out of it in a way that a fairly dim LLM
    can populate it. Hopefully.
    TODO: build an AppSpec class that maintains the structure. But, YAGNI for now.
    """
    used_keys = ["id", "ui_name", "short_hint"]
    processed_params = {}
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
        processed_params[proc_param["id"]] = proc_param
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

def get_ws_object_refs(app_spec: dict, params: dict) -> list:
    spec_params = get_processed_app_spec_params(app_spec)
    ws_objects = []
    for param in spec_params.values():
        if param["type"] == "data_object":
            param_value = params[param["id"]]
            if isinstance(param_value, list):
                ws_objects += param_value
            else:
                ws_objects.append(param_value)
    return ws_objects

def build_run_job_params(app_spec: dict, params: dict, narrative_id: int, ws_client: Workspace, release_tag: str = "release") -> dict:
    """
    This process the parameters along with the app spec to build the
    packet that gets sent to the Execution Engine's run_job command.
    This also creates a cell_id and run_id and various other required metadata.
    """
    cell_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    # TODO: validate cell_id for uniqueness from the narrative
    behavior = app_spec["behavior"]
    processed_params = map_app_params(app_spec, params, narrative_id, ws_client)
    ws_objects = get_ws_object_refs(app_spec, params)
    job_params = {
        "method": f"{behavior['kb_service_name']}.{behavior['kb_service_method']}",
        "service_ver": behavior["kb_service_version"],
        "params": processed_params,
        "app_id": app_spec["info"]["id"],
        "wsid": narrative_id,
        "meta": {
            "cell_id": cell_id,
            "run_id": run_id,
            "tag": release_tag
        }
    }
    if len(ws_objects):
        job_params["source_ws_objects"] = ws_objects

    return job_params

def map_app_params(app_spec: dict, params: dict, ws_id: int, ws_client: Workspace) -> dict:
    """
    Processes the given parameters to run the app. This returns
    the validated structure that can be passed along to the Execution
    Engine.
    """
    input_mapping = app_spec["behavior"]["kb_service_input_mapping"]
    spec_params = get_processed_app_spec_params(app_spec)

    """
    Maps the dictionary of parameters and inputs based on rules provided in
    the input_mapping. This iterates over the list of input_mappings, and
    uses them as a filter to apply to each parameter.

    Returns a list of inputs that can be passed directly to NJSW.run_job

    input_mapping is a list of dicts, as defined by
    NarrativeMethodStore.ServiceMethodInputMapping.
    params is a dict of key-value-pairs, each key is the input_parameter
    field of some parameter.
    """
    inputs_dict = {}
    for p in input_mapping:
        # 2 steps - figure out the proper value, then figure out the
        # proper position. value first!
        p_value = None
        input_param_id = None
        if "input_parameter" in p:
            input_param_id = p["input_parameter"]
            p_value = params.get(input_param_id)
            if spec_params[input_param_id]["type"] == "group":
                p_value = _map_group_inputs(
                    p_value, spec_params[input_param_id], spec_params, ws_id, ws_client
                )
            # turn empty strings into None
            if isinstance(p_value, str) and len(p_value) == 0:
                p_value = None
        elif "narrative_system_variable" in p:
            p_value = system_variable(p["narrative_system_variable"], ws_id)
        if "constant_value" in p and p_value is None:
            p_value = p["constant_value"]
        if "generated_value" in p and p_value is None:
            p_value = generate_input(p["generated_value"])

        spec_param = None
        if input_param_id:
            spec_param = spec_params[input_param_id]
        p_value = transform_param_value(
            p.get("target_type_transform"), p_value, spec_param, ws_id, ws_client
        )

        # get position!
        arg_position = p.get("target_argument_position", 0)
        target_prop = p.get("target_property")
        if target_prop is not None:
            final_input = inputs_dict.get(arg_position, {})
            if "/" in target_prop:
                # This is case when slashes in target_prop separate
                # elements in nested maps. We ignore escaped slashes
                # (separate backslashes should be escaped as well).
                bck_slash = "\u244A"
                fwd_slash = "\u20EB"
                temp_string = target_prop.replace("\\\\", bck_slash)
                temp_string = temp_string.replace("\\/", fwd_slash)
                temp_path = []
                for part in temp_string.split("/"):
                    part = part.replace(bck_slash, "\\")
                    part = part.replace(fwd_slash, "/")
                    temp_path.append(part.encode("ascii", "ignore").decode("ascii"))
                temp_map = final_input
                temp_key = None
                # We're going along the path and creating intermediate
                # dictionaries.
                for temp_path_item in temp_path:
                    if temp_key:
                        if temp_key not in temp_map:
                            temp_map[temp_key] = {}
                        temp_map = temp_map[temp_key]
                    temp_key = temp_path_item
                # temp_map points to deepest nested map now, temp_key is
                # the last item in the path
                temp_map[temp_key] = p_value
            else:
                final_input[target_prop] = p_value
            inputs_dict[arg_position] = final_input
        else:
            inputs_dict[arg_position] = p_value

    inputs_list = []
    keys = sorted(inputs_dict.keys())
    for k in keys:
        inputs_list.append(inputs_dict[k])
    return inputs_list

def transform_param_value(
    transform_type: Optional[str], value: Any, spec_param: Optional[dict], ws_id: int, ws_client: Workspace
) -> Any:
    """
    Transforms an input according to the rules given in
    NarrativeMethodStore.ServiceMethodInputMapping
    Really, there are three types of transforms possible:
      1. ref - turns the input string into a workspace ref.
      2. int - tries to coerce the input string into an int.
      3. list<type> - turns the given list into a list of the given type.
      (4.) none or None - doesn't transform.

    Returns a transformed (or not) value.

    Rules and logic, esp for objects being sent.
    1. Test if current transform applies. (None is a valid transform)
        A. Check if input is an object - valid transforms are ref, resolved-ref, list<ref>,
            list<resolved-ref>, None
        B. If not object, int, list<int>, and None are allowed.
    2. If object and not output field, apply transform as follows:
        A. None -> returns only object name
        B. ref -> returns workspace_name/object_name
        C. resolved-ref -> returns UPA
        D. (not in docs yet) upa -> returns UPA
        E. any of the above can be applied in list<X>
    3. Exception: if the input is an UPA path or reference path, it should only get transformed
        to an UPA path.

    This function will attempt to transform value according to the above rules. If value looks
    like a ref (ws_name/obj_name) and transform_type is None, then obj_name will be returned.
    Likewise, if resolved-ref is given, and value looks like an UPA already, then the already
    resolved-ref will be returned.

    Parameters:
    transform_type - str/None - should be one of the following, if not None:
        * string
        * int
        * ref
        * resolved-ref
        * upa
        * list<X> where X is any of the above
    value - anything or None. Parameter values are expected, by the KBase app stack, to
        generally be either a singleton or a list of singletons. In practice, they're usually
        strings, ints, floats, None, or a list of those.
    spec_param - either None or a spec parameter dictionary as defined by
        SpecManager.app_params. That is:
        {
            optional = boolean,
            is_constant = boolean,
            value = (whatever, optional),
            type = [text|int|float|list|textsubdata],
            is_output = boolean,
            short_hint = string,
            description = string,
            allowed_values = list (optional),
        }
    """
    if transform_type is not None:
        transform_type = transform_type.lower()
        if transform_type == "none":
            transform_type = None

    is_input_object_param = False
    if (
        spec_param is not None
        and spec_param["type"] == "text"
        and not spec_param["is_output"]
        and len(spec_param.get("allowed_types", []))
    ):
        is_input_object_param = True

    if (
        transform_type is None
        and spec_param is not None
        and spec_param["type"] == "textsubdata"
    ):
        transform_type = "string"

    if not is_input_object_param and transform_type is None:
        return value

    if transform_type in [
        "ref",
        "unresolved-ref",
        "resolved-ref",
        "putative-ref",
        "upa",
    ] or (is_input_object_param and transform_type is None):
        if isinstance(value, list):
            return [transform_object_value(transform_type, v, ws_id, ws_client) for v in value]
        return transform_object_value(transform_type, value, ws_id, ws_client)

    if transform_type == "int":
        # make it an integer, OR 0.
        if value is None or len(str(value).strip()) == 0:
            return None
        return int(value)

    if transform_type == "string":
        if value is None:
            return value
        if isinstance(value, list):
            return ",".join(value)
        if isinstance(value, dict):
            return ",".join([f"{key}={value[key]}" for key in value])
        return str(value)

    if transform_type.startswith("list<") and transform_type.endswith(">"):
        # make it a list of transformed types.
        list_type = transform_type[5:-1]
        if isinstance(value, list):
            return [transform_param_value(list_type, v, None, ws_id, ws_client) for v in value]
        return [transform_param_value(list_type, value, None, ws_id, ws_client)]

    else:
        raise ValueError("Unsupported Transformation type: " + transform_type)


def transform_object_value(
    transform_type: Optional[str], value: Optional[str], ws_id: int, ws_client: Workspace
) -> Optional[str]:
    """
    Cases:
    transform = ref, unresolved-ref, or putative-ref:
        - should return wsname / object name
    transform = upa or resolved-ref:
        - should return UPA
    transform = None:
        - should return object name
    Note that if it is a reference path, it was always get returned as an UPA-path
    for the best compatibility.

    value can be either object name, ref, upa, or ref-path
    can tell by testing with UPA api

    If we can't find any object info on the value, just return the value as-is

    "putative-ref" is a special case where the value is an object name and the object may or
    may not exist. It is used to deal with the input from SpeciesTreeBuilder; if that app gets
    fixed, it can be removed.

    """
    if value is None:
        return None

    # 1. get object info
    is_upa = test_is_upa(value)
    is_ref = test_is_ref(value)
    is_path = (is_upa or is_ref) and ";" in value

    # simple cases:
    # 1. if is_upa and we want resolved-ref or upa, return the value
    # 2. if is_ref and not is_upa and we want ref or unresolved-ref, return the value
    # 3. if is neither upa or ref and transform is None, then we want the string, so return that
    # 4. Otherwise, look up the object and return what's desired from there.

    if is_upa and transform_type in ["upa", "resolved-ref"]:
        return value
    if (
        not is_upa
        and is_ref
        and transform_type in ["ref", "unresolved-ref", "putative-ref"]
    ):
        return value
    if not is_upa and not is_ref and transform_type is None:
        return value

    search_ref = value
    if not is_upa and not is_ref:
        search_ref = f"{ws_id}/{value}"
    try:
        obj_info = ws_client.get_object_info(search_ref, include_path=True)
    except Exception as e:
        # a putative-ref can be an extant or a to-be-created object; if the object
        # is not found, the workspace name/object name can be returned
        if transform_type == "putative-ref" and (
            "No object with name" in str(e) or "No object with id" in str(e)
        ):
            return search_ref

        transform = transform_type
        if transform is None:
            transform = "object name"
        raise ValueError(
            f"Unable to find object reference '{search_ref}' to transform as {transform}: "
            + str(e)
        )

    if is_path or transform_type in ["resolved-ref", "upa"]:
        return ";".join(obj_info["path"])
    if transform_type in ["ref", "unresolved-ref", "putative-ref"]:
        return f"{obj_info['ws_name']}/{obj_info['name']}"
    if transform_type is None:
        return obj_info["name"]
    return value


def generate_input(generator: dict) -> str:
    """
    Generates an input value using rules given by
    NarrativeMethodStore.AutoGeneratedValue.
    generator - dict
        has 3 optional properties:
        prefix - if present, is prepended to the generated string.
        symbols - if present is the number of symbols to autogenerate (if
                    not present, default=8)
        suffix - if present, is appended to the generated string.
    So, if generator is None or an empty dict, returns an 8-symbol string.
    """
    symbols = 8
    if "symbols" in generator:
        try:
            symbols = int(generator["symbols"])
        except BaseException:
            raise ValueError(
                'The "symbols" input to the generated value must be an '
                + "integer > 0!"
            ) from None
    if symbols < 1:
        raise ValueError("Must have at least 1 symbol to randomly generate!")
    ret = "".join([chr(random.randrange(0, 26) + ord("A")) for _ in range(symbols)])
    if "prefix" in generator:
        ret = str(generator["prefix"]) + ret
    if "suffix" in generator:
        return ret + str(generator["suffix"])
    return ret


def system_variable(var: str, narrative_id: int) -> str | int | None:
    """
    Returns a KBase system variable. Just a little wrapper.

    Parameters
    ----------
    var: string, one of "workspace", "workspace_id", "token", "user_id",
        "timestamp_epoch_ms", "timestamp_epoch_sec"
        workspace - returns the KBase workspace name
        workspace_id - returns the numerical id of the current workspace
        token - returns the current user's token credential
        user_id - returns the current user's id
        timestamp_epoch_ms - the current epoch time in milliseconds
        timestamp_epoch_sec - the current epoch time in seconds

    if anything is not found, returns None
    """
    var = var.lower()
    if var == "workspace" or var == "workspace_id":
        return narrative_id
    elif var == "user_id":
        return None
    elif var == "timestamp_epoch_ms":
        # get epoch time in milliseconds
        return int(time.time() * 1000)
    elif var == "timestamp_epoch_sec":
        # get epoch time in seconds
        return int(time.time())
    return None

def test_is_upa(upa: str) -> bool:
    """
    Returns True if the given upa string is valid, False, otherwise.
    """
    return re.match(r"^\d+(\/\d+){2}(;\d+(\/\d+){2})*$", upa) is not None

def test_is_ref(ref: str) -> bool:
    """
    Returns True if the given string is a reference or upa, False otherwise.
    That is, if it has this structure:
    blahblah/blahblah
    or
    1/2
    or
    1/2/3
    or
    blahblah/blahblah/1
    """
    if test_is_upa(ref):
        return True
    split_path = ref.split(";")
    for sub_ref in split_path:
        c = sub_ref.count("/")
        if c < 1 or c > 2:
            return False
    return True

def _map_group_inputs(value: Any, spec_param: dict, spec_params: list, ws_id: int, ws_client: Workspace) -> dict:
    if isinstance(value, list):
        return [_map_group_inputs(v, spec_param, spec_params, ws_client) for v in value]

    if value is None:
        return None

    mapped_value = {}
    id_map = spec_param.get("id_mapping", {})
    for param_id in id_map:
        # ensure that the param referenced in the group param list
        # exists in the spec.
        # NB: This should really never happen if the sdk registration
        # process validates them.
        if param_id not in spec_params:
            msg = "Unknown parameter id in group mapping: " + param_id
            raise ValueError(msg)
    for param_id in value:
        target_key = id_map.get(param_id, param_id)
        # Sets either the raw value, or if the parameter is an object
        # reference the full object refernce (see the method).
        if value[param_id] is None:
            target_val = None
        else:
            target_val = resolve_ref_if_typed(
                value[param_id], spec_params[param_id], ws_id, ws_client
            )

        mapped_value[target_key] = target_val
    return mapped_value

def resolve_single_ref(ws_id: int, value: str, ws_client: Workspace) -> str:
    # TODO: fix this. It's weird and likely broken.
    ret = None
    if "/" in value:
        path_items = [item.strip() for item in value.split(";")]
        for path_item in path_items:
            if len(path_item.split("/")) > 3:
                raise ValueError(
                    f"Object reference {value} has too many slashes - should be ws/object/version"
                )
        info = ws_client.get_object_info(value)
        path_items[len(path_items) - 1] = f"{info['ws_id']}/{info['obj_id']}/{info['version']}"
        ret = ";".join(path_items)
    # Otherwise, assume it's a name, not a reference.
    else:
        info = ws_client.get_object_info(f"{ws_id}/{value}")
        ret = f"{info['ws_id']}/{info['obj_id']}/{info['version']}"
    return ret


def resolve_ref(ws_id: int, value: str, ws_client: Workspace) -> str:
    if isinstance(value, list):
        return [resolve_single_ref(ws_id, v, ws_client) for v in value]
    else:
        return resolve_single_ref(ws_id, value, ws_client)


def resolve_ref_if_typed(value: str, spec_param: dict, ws_id: int, ws_client: Workspace) -> str:
    """
    For a given value and associated spec, if this is not an output param,
    then ensure that the reference points to an object in the current
    workspace, and transform the value into an absolute reference to it.
    """
    is_output = "is_output" in spec_param and spec_param["is_output"] == 1
    if "allowed_types" in spec_param and not is_output:
        allowed_types = spec_param["allowed_types"]
        if len(allowed_types) > 0:
            return resolve_ref(ws_id, value, ws_client)
    return value
