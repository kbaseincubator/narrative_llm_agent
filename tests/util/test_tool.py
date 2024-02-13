from narrative_llm_agent.util.tool import process_tool_input
import pytest

@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("foo", "foo"),
        (None, None),
        (123, "123"),
        ('{"foo": "bar"}', "bar"),
        ('{"bar": "bar"}', None)
    ]
)
def test_process_tool_input(test_input, expected):
    key = "foo"
    val = process_tool_input(test_input, key)
    assert val == expected
