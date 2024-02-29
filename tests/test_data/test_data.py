import json
from pathlib import Path

def get_test_narrative(as_dict=False) -> str | dict:
    test_narr_path = Path(__file__).parent / "test_narrative.json"
    with open(test_narr_path) as infile:
        test_narr = infile.read()
    if as_dict:
        return json.loads(test_narr)
    return test_narr
