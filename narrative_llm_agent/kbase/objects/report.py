import json

REPORT_TYPE = "KBaseReport.Report"


class LinkedFile:
    handle: str
    description: str
    name: str
    label: str
    url: str

    def __init__(self, file_link: dict) -> None:
        for key in ["handle", "description", "name", "label", "URL"]:
            self.__setattr__(key.lower(), file_link.get(key, ""))


class KBaseReport:
    raw: dict
    html_links: list[LinkedFile]
    file_links: list[LinkedFile]
    text_message: str
    direct_html: str
    direct_html_link_index: int
    warnings: list[str]

    def __init__(self, report_obj: dict) -> None:
        # process into an easy-to-handle report object.
        # could probably also use a NamedTuple or something here.
        # but this should suffice to start
        self.raw = report_obj
        self.text_message = report_obj.get("text_message", "")
        self.direct_html = report_obj.get("direct_html", "")
        self.direct_html_link_index = report_obj.get("direct_html_link_index", None)
        self.warnings = report_obj.get("warnings", [])

        self.html_links = [LinkedFile(link) for link in report_obj.get("html_links", [])]
        self.file_links = [LinkedFile(link) for link in report_obj.get("file_links", [])]

    def __str__(self):
        return json.dumps(self.raw)


def is_report(obj_type: str) -> bool:
    if not isinstance(obj_type, str):
        return False
    return REPORT_TYPE in obj_type
