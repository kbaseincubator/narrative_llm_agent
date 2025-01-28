from pydantic import BaseModel


REPORT_TYPE = "KBaseReport.Report"


class CreatedObject(BaseModel):
    description: str | None = ""
    ref: str | None = ""


class LinkedFile(BaseModel):
    handle: str | None = None
    description: str | None = None
    name: str | None = None
    label: str | None = None
    URL: str | None = None


class KBaseReport(BaseModel):
    html_links: list[LinkedFile] | None = []
    file_links: list[LinkedFile] | None = []
    text_message: str | None = ""
    direct_html: str | None = ""
    direct_html_link_index: int | None = None
    warnings: list[str] | None = []
    html_window_height: int | None = None
    objects_created: list[CreatedObject] | None = []
    summary_window_height: int | None = None


def is_report(obj_type: str) -> bool:
    if not isinstance(obj_type, str):
        return False
    return REPORT_TYPE in obj_type
