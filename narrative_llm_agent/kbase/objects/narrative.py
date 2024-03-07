import json
import time
import uuid
from typing import Any, Dict, List

from narrative_llm_agent.util.tool import convert_to_boolean

NARRATIVE_ID_KEY: str = "narrative"
NARRATIVE_NAME_KEY: str = "narrative_nice_name"
NARRATIVE_TYPE: str = "KBaseNarrative.Narrative"


class AppSpec:
    pass


class JobInfo:
    pass


class Cell:
    raw: dict
    cell_type: str
    source: str

    def __init__(self, cell_type: str, raw_cell: Dict[str, Any]) -> None:
        self.raw = raw_cell
        self.cell_type = cell_type
        self.source = raw_cell.get("source", "")

    def get_info_str(self):
        """
        The Cell info str returns jupyter.<cell type>.
        If a different format is required, override this function.
        """
        return f"jupyter.{self.cell_type}"

    def to_dict(self):
        return self.raw


class CodeCell(Cell):
    outputs: List[Any] = []

    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("code", cell_dict)
        if "outputs" in cell_dict and cell_dict["outputs"] is not None:
            self.outputs = cell_dict["outputs"]


class RawCell(Cell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("raw", cell_dict)


class MarkdownCell(Cell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("markdown", cell_dict)


class KBaseCell(CodeCell):
    kb_cell_type: str

    def __init__(self, kb_cell_type: str, cell_dict: Dict[str, Any]) -> None:
        super().__init__(cell_dict)
        self.kb_cell_type = kb_cell_type

    def get_info_str(self):
        return f"kbase.{self.kb_cell_type}"


class AppCell(KBaseCell):
    app_spec: AppSpec
    app_id: str
    app_name: str
    job_info: JobInfo

    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("KBaseApp", cell_dict)
        self.app_spec = None
        self.app_id = None
        self.app_name = None
        self.job_info = None

    def get_info_str(self):
        spec_info = self.raw["metadata"]["kbase"].get("appCell", {}).get("app")
        return f"method.{spec_info['id']}/{spec_info['gitCommitHash']}"


class BulkImportCell(KBaseCell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("KBaseBulkImport", cell_dict)

    def get_info_str(self):
        return "kbase.bulk_import"


class DataCell(KBaseCell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("KBaseData", cell_dict)

    def get_info_str(self):
        return "kbase.data_viewer"


class OutputCell(KBaseCell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("KBaseOutput", cell_dict)

    def get_info_str(self):
        return "kbase.app_output"


class NarrativeMetadata:
    creator: str
    data_dependencies: List[str]
    description: str
    format: str = "ipynb"
    name: str
    is_temporary: bool
    raw: Dict[str, Any]

    def __init__(self, narr_meta: Dict[str, Any]) -> None:
        self.creator = narr_meta.get("creator", "unknown")
        self.data_dependencies = narr_meta.get("data_dependencies", [])
        self.description = narr_meta.get("description", "")
        self.format = narr_meta.get("format", "ipynb")
        self.name = narr_meta.get("name", "unknown narrative")
        self.is_temporary = convert_to_boolean(narr_meta.get("is_temporary"))
        self.raw = narr_meta

    def to_dict(self):
        return self.raw


class Narrative:
    nbformat: int
    nbformat_minor: int
    metadata: NarrativeMetadata
    cells: List[Cell]

    def __init__(self, narr_dict: Dict[str, Any]) -> None:
        if "cells" not in narr_dict:
            raise ValueError(
                "'cells' key not found, this might be a VERY old narrative. Please update it before continuing."
            )
        self.metadata = NarrativeMetadata(narr_dict.get("metadata", {}))
        self.nbformat = narr_dict.get("nbformat")
        self.nbformat_minor = narr_dict.get("nbformat_minor")
        self.cells = [Narrative.make_cell_from_dict(cell) for cell in narr_dict["cells"]]
        self.raw = narr_dict

    @classmethod
    def make_cell_from_dict(cls, cell_dict: Dict[str, Any]) -> Cell:
        # route to the right cell constructor
        meta = cell_dict.get("metadata", {})
        if "kbase" not in meta or "type" not in meta["kbase"]:
            if cell_dict["cell_type"] == "code":
                return CodeCell(cell_dict)
            elif cell_dict["cell_type"] == "markdown":
                return MarkdownCell(cell_dict)
            elif cell_dict["cell_type"] == "raw":
                return RawCell(cell_dict)
            else:
                return Cell("unknown", cell_dict)
        kbase_type = meta["kbase"]["type"]
        if kbase_type == "app":
            return AppCell(cell_dict)
        elif kbase_type == "data":
            return DataCell(cell_dict)
        elif kbase_type == "output":
            return OutputCell(cell_dict)
        elif kbase_type == "app-bulk-import":
            return BulkImportCell(cell_dict)
        elif kbase_type == "code":
            return CodeCell(cell_dict)
        elif kbase_type == "markdown":
            return MarkdownCell(cell_dict)
        else:
            return Cell("unknown", cell_dict)

    def add_markdown_cell(self, text: str) -> MarkdownCell:
        """
        Adds a markdown cell to the Narrative and returns it.
        """
        cell_dict = self._create_cell_dict("markdown", "markdown", text)
        new_cell = MarkdownCell(cell_dict)
        self.cells.append(new_cell)
        self.raw["cells"].append(cell_dict)
        return new_cell

    def add_code_cell(self, source: str, outputs: list = []) -> CodeCell:
        """
        Adds a code cell to the Narrative and returns it.
        """
        cell_dict = self._create_cell_dict("code", "code", source, outputs=outputs)
        new_cell = CodeCell(cell_dict)
        self.cells.append(new_cell)
        self.raw["cells"].append(cell_dict)
        return new_cell

    def _create_cell_dict(
        self, cell_type: str, kbase_cell_type: str, source: str, outputs: list = []
    ) -> dict[str, Any]:
        return {
            "cell_type": cell_type,
            "source": source,
            "outputs": outputs,
            "metadata": {"kbase": self._create_kbase_meta(kbase_cell_type)},
        }

    def _create_kbase_meta(self, kbase_cell_type: str) -> dict[str, Any]:
        """
        TODO: fix this up for real and make it more robust.
        """
        title = "Code Cell"
        icon = "code"
        if kbase_cell_type == "markdown":
            icon = "paragraph"

        meta = {
            "attributes": {
                "created": time.gmtime(),
                "id": self._get_new_cell_id(),
                "title": title,
                "icon": icon,
            },
            "type": kbase_cell_type,
        }
        return meta

    def _get_new_cell_id(self) -> str:
        new_id = str(uuid.uuid4())
        # check all cells
        while self._is_duplicate_id(new_id):
            new_id = str(uuid.uuid4())
        return new_id

    def _is_duplicate_id(self, cell_id: str) -> bool:
        for cell in self.cells:
            cell_meta = cell.raw.get("metadata", {})
            if "kbase" in cell_meta and "attributes" in cell_meta["kbase"]:
                if cell_meta["kbase"]["attributes"].get("id") == cell_id:
                    return True
        return False

    def to_dict(self):
        return {
            "cells": [cell.to_dict() for cell in self.cells],
            "metadata": self.metadata.to_dict(),
            "nbformat": self.nbformat,
            "nbformat_minor": self.nbformat_minor,
        }

    def get_cell_counts(self):
        """
        Returns a dictionary of cell counts. Keys are one of
        jupyter.markdown
        jupyter.code
        jupyter.raw
        or apps, with this format:
        method.{app_id}/{app version hash}

        values are the counts of how many of those cells there are
        """
        cell_counts = {}
        for cell in self.cells:
            cell_info_str = cell.get_info_str()
            if cell_info_str not in cell_counts:
                cell_counts[cell_info_str] = 1
            else:
                cell_counts[cell_info_str] += 1
        return cell_counts

    def __str__(self):
        return json.dumps(self.to_dict())


def is_narrative(obj_type: str) -> bool:
    if not isinstance(obj_type, str):
        return False
    return obj_type.startswith(NARRATIVE_TYPE)
