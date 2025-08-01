from typing import Any, Optional
import uuid
import time
import random
import re
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.objects.app_spec import (
    AppSpec,
    AppParameter,
    AutoGeneratedValue,
)


def get_processed_app_spec_params(
    spec: AppSpec, separate_group_params: bool = True
) -> dict:
    """
    TODO: check all existing specs to see if parameters show up in multiple groups.
    'cause if so, that's going to give me a headache. Assume for now that they don't.
    """
    used_keys = ["id", "ui_name", "short_hint"]
    processed_params = {}
    for param in spec.parameters:
        proc_param = {key: getattr(param, key) for key in used_keys}
        proc_param["is_output_object"] = False
        param_type, allowed_values = process_param_type(param)
        proc_param["type"] = param_type
        if (
            param_type == "data_object"
            and param.text_options is not None
            and param.text_options.is_output_name == 1
        ):
            proc_param["is_output_object"] = True
        allowed_key = "allowed"
        if param_type == "int" or param_type == "float":
            allowed_key = "allowed_range"
        if param_type == "data_object":
            allowed_key = "allowed_data_type"
        proc_param[allowed_key] = allowed_values
        proc_param["multiple"] = True if param.allow_multiple == 1 else False
        proc_param["optional"] = True if param.optional == 1 else False

        proc_param["default_value"] = process_default_values(param, param_type)

        processed_params[proc_param["id"]] = proc_param
    processed_param_groups = {}
    if spec.parameter_groups is not None:
        for group in spec.parameter_groups:
            param_group = {
                "id": group.id,
                "ui_name": group.ui_name,
                "short_hint": group.short_hint,
                "params": {
                    param_id: processed_params[param_id]
                    for param_id in group.parameter_ids
                },
                "optional": True if group.optional == 1 else False,
                "as_list": True if group.allow_multiple == 1 else False,
                "type": "group",
            }
            if separate_group_params:
                for param_id in group.parameter_ids:
                    del processed_params[param_id]
            processed_param_groups[group.id] = param_group
    return processed_params | processed_param_groups


def process_default_values(param: AppParameter, param_type: str) -> str | int | None:
    defaults = param.default_values
    if defaults is None:
        return None
    if len(defaults) and len(defaults[0]):
        return _cast_default_param_value(param_type, defaults[0])
    return None

def _cast_default_param_value(param_type: str, value: Any) -> Any:
    """
    Casts a value to match parameter type.
    Most types are text, so nothing is done.
    Empty strings are returned as None for ints, floats, and dropdowns.
    This really only gets called by process_default_values, so in theory the
    value=None and int/"" cases won't actually happen following that route,
    but this might get used later to post-process LLM-built params, so leaving that in.
    """
    if value is None:
        return None
    if param_type in {"text", "textarea", "textsubdata", "checkbox", "radio", "tab", "file", "dynamic_dropdown"}:
        return value
    if param_type == "int":
        if value == "" or value.lower() == "null":  # I hate people.
            return None
        return int(value)
    if param_type == "float":
        if value == "" or value.lower() == "null":  # I really hate people.
            return None
        return float(value)
    if param_type == "dropdown" and value == "":
        return None
    return value

def process_param_type(param: AppParameter) -> tuple:
    """
    Processes the type of parameter this is.
    Expands on the KBase typespec to include "data_object" and others
    """
    field_type = param.field_type
    allowed_values = []
    # allowed field_type values text | textarea | textsubdata | intslider |
    # floatslider | checkbox | dropdown | radio | tab | file | dynamic_dropdown
    if field_type == "text" and param.text_options is not None:
        opts = param.text_options
        if opts.valid_ws_types is not None:
            field_type = "data_object"
            allowed_values = opts.valid_ws_types
        elif opts.validate_as is not None:
            valid_type = opts.validate_as.lower()
            if valid_type in ["int", "float"]:
                field_type = valid_type
                min_val = getattr(opts, f"min_{valid_type}")
                if min_val is None:
                    min_val = float("-inf")
                max_val = getattr(opts, f"max_{valid_type}")
                if max_val is None:
                    max_val = float("inf")
                allowed_values = [min_val, max_val]
    if field_type == "dropdown" and param.dropdown_options is not None:
        allowed_values = [
            {
                "name": opt.display,
                "value": opt.value
            }
            for opt in param.dropdown_options.options
        ]
    # TODO types-
    # textsubdata
    # dynamic_dropdown
    # these both depend on external data sources.
    # not exactly necessary to start with, I don't think.
    return (field_type, allowed_values)


def get_ws_object_refs(app_spec: AppSpec, params: dict) -> list:
    spec_params = get_processed_app_spec_params(app_spec)
    ws_objects = []
    for param in spec_params.values():
        if param["type"] == "data_object" and not param["is_output_object"]:
            param_value = params.get(param["id"])
            if param_value is not None:
                if isinstance(param_value, list):
                    ws_objects += param_value
                else:
                    ws_objects.append(param_value)
    return ws_objects


def build_run_job_params(
    app_spec: AppSpec,
    params: dict,
    narrative_id: int,
    ws_client: Workspace,
    release_tag: str = "release",
) -> dict:
    """
    This process the parameters along with the app spec to build the
    packet that gets sent to the Execution Engine's run_job command.
    This also creates a cell_id and run_id and various other required metadata.
    """
    cell_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    # TODO: validate cell_id for uniqueness from the narrative
    behavior = app_spec.behavior
    processed_params = map_app_params(app_spec, params, narrative_id, ws_client)
    ws_objects = get_ws_object_refs(app_spec, params)
    job_params = {
        "method": f"{behavior.kb_service_name}.{behavior.kb_service_method}",
        "service_ver": behavior.kb_service_version,
        "params": processed_params,
        "app_id": app_spec.info.id,
        "wsid": int(narrative_id),
        "meta": {"cell_id": cell_id, "run_id": run_id, "tag": release_tag},
    }
    if len(ws_objects):
        job_params["source_ws_objects"] = ws_objects

    return job_params


def validate_params(params: dict, spec_params: dict) -> None:
    """
    If valid, returns None
    If invalid, raises a ValueError with one or more string errors.
    """
    return None

def map_app_params(
    app_spec: AppSpec, params: dict, ws_id: int, ws_client: Workspace
) -> dict:
    """
    Processes the given parameters to run the app. This returns
    the validated structure that can be passed along to the Execution
    Engine.
    """
    input_mapping = app_spec.behavior.kb_service_input_mapping
    spec_params = get_processed_app_spec_params(app_spec, separate_group_params=False)
    validate_params(params, spec_params)

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
        if p.input_parameter is not None:
            input_param_id = p.input_parameter
            p_value = params.get(input_param_id)
            if spec_params[input_param_id]["type"] == "group":
                p_value = _map_group_inputs(
                    p_value, spec_params[input_param_id], spec_params, ws_id, ws_client
                )
            # turn empty strings into None
            if isinstance(p_value, str) and len(p_value) == 0:
                p_value = None
        elif p.narrative_system_variable is not None:
            p_value = system_variable(p.narrative_system_variable, ws_id, ws_client)
        if p.constant_value and p_value is None:
            p_value = p.constant_value
        if p.generated_value and p_value is None:
            p_value = generate_input(p.generated_value)

        spec_param = None
        if input_param_id:
            spec_param = spec_params[input_param_id]
        p_value = transform_param_value(
            p.target_type_transform, p_value, spec_param, ws_id, ws_client
        )

        # get position!
        arg_position = p.target_argument_position or 0
        target_prop = p.target_property
        if target_prop is not None:
            final_input = inputs_dict.get(arg_position, {})
            if "/" in target_prop:
                # This is case when slashes in target_prop separate
                # elements in nested maps. We ignore escaped slashes
                # (separate backslashes should be escaped as well).
                bck_slash = "\u244a"
                fwd_slash = "\u20eb"
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
    transform_type: Optional[str],
    value: Any,
    spec_param: Optional[dict],
    ws_id: int,
    ws_client: Workspace,
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
        and not spec_param["is_output_object"]
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
            return [
                transform_object_value(transform_type, v, ws_id, ws_client)
                for v in value
            ]
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
            return [
                transform_param_value(list_type, v, None, ws_id, ws_client)
                for v in value
            ]
        return [transform_param_value(list_type, value, None, ws_id, ws_client)]

    else:
        raise ValueError("Unsupported Transformation type: " + transform_type)


def transform_object_value(
    transform_type: Optional[str],
    value: Optional[str],
    ws_id: int,
    ws_client: Workspace,
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
    is_upa = is_valid_upa(value)
    is_ref = is_valid_ref(value)
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
        obj_info = ws_client.get_object_info(search_ref)
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
        return ";".join(obj_info.path)
    if transform_type in ["ref", "unresolved-ref", "putative-ref"]:
        return f"{obj_info.ws_name}/{obj_info.name}"
    if transform_type is None:
        return obj_info.name
    return value


def generate_input(generator: AutoGeneratedValue) -> str:
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
    if generator.symbols is not None:
        try:
            symbols = int(generator.symbols)
        except BaseException:
            raise ValueError(
                'The "symbols" input to the generated value must be an '
                + "integer > 0!"
            ) from None
    if symbols < 1:
        raise ValueError("Must have at least 1 symbol to randomly generate!")
    ret = "".join([chr(random.randrange(0, 26) + ord("A")) for _ in range(symbols)])
    if generator.prefix is not None:
        ret = str(generator.prefix) + ret
    if generator.suffix is not None:
        return ret + str(generator.suffix)
    return ret


def system_variable(
    var: str, narrative_id: int, ws_client: Workspace
) -> str | int | None:
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
    if var == "workspace":
        ws_info = ws_client.get_workspace_info(int(narrative_id))
        return ws_info.name
    elif var == "workspace_id":
        return int(narrative_id)
    elif var == "user_id":
        return None  # TODO: not implemented yet
    elif var == "timestamp_epoch_ms":
        # get epoch time in milliseconds
        return int(time.time() * 1000)
    elif var == "timestamp_epoch_sec":
        # get epoch time in seconds
        return int(time.time())
    return None


def is_valid_upa(upa: str) -> bool:
    """
    Returns True if the given upa string is valid, False, otherwise.
    """
    if not isinstance(upa, str):
        return False
    return re.match(r"^\d+(\/\d+){2}(;\d+(\/\d+){2})*$", upa) is not None


def is_valid_ref(ref: str) -> bool:
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
    if not isinstance(ref, str):
        return False
    if is_valid_upa(ref):
        return True
    split_path = ref.split(";")
    for sub_ref in split_path:
        c = sub_ref.count("/")
        if c < 1 or c > 2:
            return False
    return True


def _map_group_inputs(
    value: Any, spec_param: dict, spec_params: list, ws_id: int, ws_client: Workspace
) -> dict:
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


def resolve_single_ref(value: str, ws_id: int, ws_client: Workspace) -> str:
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
        path_items[len(path_items) - 1] = info.upa
        ret = ";".join(path_items)
    # Otherwise, assume it's a name, not a reference.
    else:
        info = ws_client.get_object_info(f"{ws_id}/{value}")
        ret = info.upa
    return ret


def resolve_ref(
    value: str | list[str], ws_id: int, ws_client: Workspace
) -> str | list[str]:
    """
    Resolves a Workspace object reference (or list of references). A "reference" is a
    string with a workspace id (or name), object id (or name), and an optional version.
    This resolves the reference(s) to one or more UPAs.
    If the objects don't exist, or the user doesn't have access to them, this raises a
    ServerError
    # TODO: make WorkspaceError exception
    """
    if isinstance(value, list):
        return [resolve_single_ref(v, ws_id, ws_client) for v in value]
    else:
        return resolve_single_ref(value, ws_id, ws_client)


def resolve_ref_if_typed(
    value: str | list[str], spec_param: dict, ws_id: int, ws_client: Workspace
) -> str | list[str]:
    """
    For a given value and associated spec, if this is not an output param,
    then ensure that the reference points to an object in the current
    workspace, and transform the value into an absolute reference to it.
    """
    is_output = spec_param.get("is_output_object", False)
    if spec_param["type"] == "data_object" and not is_output:
        return resolve_ref(value, ws_id, ws_client)
    return value


def map_inputs_from_job(job_inputs: dict | list, app_spec: dict) -> dict:
    """
    Unmaps the actual list of job inputs back to the parameters specified by app_spec.
    For example, the inputs given to a method might be a list like this:
    ['input1', {'ws': 'my_workspace', 'foo': 'bar'}]
    and the input mapping looks like:
    [{
        'target_position': 0,
        'input_parameter': 'an_input'
    },
    {
        'target_position': 1,
        'target_property': 'ws',
        'input_parameter': 'workspace'
    },
    {
        'target_position': 1,
        'target_property': 'foo',
        'input_parameter': 'baz'
    }]
    this would return:
    {
        'an_input': 'input1',
        'workspace': 'my_workspace',
        'baz': 'bar'
    }
    This only covers those parameters from the input_mapping that come with an input_parameter
    field. system variables, constants, etc., are ignored - this function just goes back to the
    original inputs set by the user.
    """
    input_dict = {}
    spec_inputs = app_spec["behavior"]["kb_service_input_mapping"]

    # expect the inputs to be valid. so things in the expected position should be the
    # right things (either dict, list, singleton)
    for param in spec_inputs:
        if "input_parameter" not in param:
            continue
        input_param = param.get("input_parameter", None)
        position = param.get("target_position", 0)
        prop = param.get("target_property", None)
        value = job_inputs[position]
        if prop is not None:
            value = value.get(prop, None)

        # that's the value. Now, if it was transformed, try to transform it back.
        if param.get("target_type_transform") is not None:
            transform_type = param["target_type_transform"]
            if transform_type.startswith("list") and isinstance(value, list):
                inner_transform = transform_type[5:-1]
                for i in range(len(value)):
                    value[i] = _untransform(inner_transform, value[i])
            else:
                value = _untransform(transform_type, value)

        input_dict[input_param] = value
    return input_dict


def _untransform(transform_type: str, value: str) -> str:
    if transform_type in ["ref", "putative-ref", "unresolved-ref"] and isinstance(
        value, str
    ):
        # shear off everything before the first '/' - there should just be one.
        slash = value.find("/")
        if slash == -1:
            return value
        return value[slash + 1 :]
    return value
