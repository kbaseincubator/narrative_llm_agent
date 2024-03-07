import json
import numbers


def process_tool_input(input_val, expected_key: str) -> str:
    """
    Post-processes a tool input. Agents and some LLMs seem to really like sending inputs
    to tools not just as the input string but as a dictionary with that string.
    So if there's a tool like

    def do_things(input_val: str) -> str:
        ...

    it'll often get invoked as
    do_things({"input_val": "some input"})

    instead of
    do_things("some input")

    This looks at the input and unpacks it if it's a JSON string and returns the expected
    key if present, or None otherwise.

    If it's not a JSON string, it just returns the value.
    """
    if input_val is None:
        return None
    if isinstance(input_val, dict):
        return input_val.get(expected_key, None)
    if isinstance(input_val, numbers.Number):
        return str(input_val)
    if not isinstance(input_val, str):
        return None
    try:
        input_json = json.loads(input_val)
        if expected_key in input_json:
            return str(input_json[expected_key])
        return None
    except json.JSONDecodeError:
        return str(input_val)


def convert_to_boolean(param: bool | int | float | str) -> bool:
    """
    Takes in a parameter of type bool, int, float, or str and converts
    it (more or less logically speaking) to a boolean value. It mostly
    defaults to True if there's any question.
    * bools are passed back as-is
    * ints and floats are False if 0, True otherwise
    * strings are False if the string contains the word "false", True otherwise
    * None values are always False
    * all other values (lists, dicts, other objects) default to True
    """
    if param is None:
        return False
    if isinstance(param, bool):
        return param
    if isinstance(param, str):
        lower_str = param.lower()
        if "false" in lower_str or len(lower_str) == 0:
            return False
        return True
    if param == 0:
        return False
    return True
