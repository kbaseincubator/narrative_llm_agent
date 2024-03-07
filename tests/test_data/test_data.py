import json
from pathlib import Path

def load_test_data_json(file_path: Path, parse_json: bool=True) -> str | list | dict:
    """
    Loads some JSON test data. If parse_json == False, this just returns the
    file contents as a string and doesn't parse the JSON.

    file_path is expected to be relative to tests/test_data (i.e. in this
    directory)
    """
    with open(Path(__file__).parent / file_path) as infile:
        data = infile.read()
    if parse_json:
        return json.loads(data)
    return data

def get_test_narrative(as_dict=False) -> str | dict:
    return load_test_data_json(Path("test_narrative.json"), parse_json=as_dict)

def get_test_report(report_type: str, file_url: str=None, html_url: str=None) -> dict:
    """
    Allowed report types:
    fastqc
    other
    """

    if report_type == "fastqc":
        report_path = Path("test_fastqc_report.json")
    elif report_type == "other":
        report_path = Path("test_other_report.json")
    else:
        raise ValueError(f"unknown report type {report_type}")
    report = load_test_data_json(report_path)
    if file_url is not None:
        for file in report["data"]["file_links"]:
            if "URL" in file:
                file["URL"] = file_url
    if html_url is not None:
        for html in report["data"]["html_links"]:
            if "URL" in html:
                html["URL"] = html_url
    return report
