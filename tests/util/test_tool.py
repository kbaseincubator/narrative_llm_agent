import pytest

from narrative_llm_agent.util.tool import convert_to_boolean, process_tool_input


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("foo", "foo"),
        (None, None),
        (123, "123"),
        ('{"foo": "bar"}', "bar"),
        ('{"bar": "bar"}', None),
        ([], None),
        ({"foo": "bar"}, "bar"),
        ({"not_foo": "bar"}, None),
    ],
)
def test_process_tool_input(test_input, expected):
    key = "foo"
    val = process_tool_input(test_input, key)
    assert val == expected


true_booleans = ["foo", "true", "truthy", True, 1, "1", [], {}, 0.0001, 1.5, convert_to_boolean]


@pytest.mark.parametrize("test_input", [(truthy) for truthy in true_booleans])
def test_convert_to_boolean_true(test_input):
    assert convert_to_boolean(test_input) is True


false_booleans = [False, "false", "is false", 0, None]


@pytest.mark.parametrize("test_input", [(falsy) for falsy in false_booleans])
def test_convert_to_boolean_false(test_input):
    assert convert_to_boolean(test_input) is False
