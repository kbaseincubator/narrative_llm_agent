import json
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.util.tool import convert_to_boolean
from typing import List, Any, Dict

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

    def to_dict(self):
        return self.raw

class CodeCell(Cell):
    outputs: List[Any] = []
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__("code", cell_dict)
        if "outputs" in cell_dict:
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

class AppCell(KBaseCell):
    app_spec: AppSpec
    app_id: str
    app_name: str
    job_info: JobInfo

    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__('KBaseApp', cell_dict)

class BulkImportCell(KBaseCell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__('KBaseBulkImport', cell_dict)

class DataCell(KBaseCell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__('KBaseData', cell_dict)

class OutputCell(KBaseCell):
    def __init__(self, cell_dict: Dict[str, Any]) -> None:
        super().__init__('KBaseOutput', cell_dict)


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
        self.format = narr_meta.get("format")
        self.name = narr_meta.get("name", "unknown narrative")
        self.is_temporary = convert_to_boolean(narr_meta["is_temporary"])
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
            raise ValueError("'cells' key not found, this might be a VERY old narrative. Please update it before continuing.")
        self.metadata = NarrativeMetadata(narr_dict.get("metadata", {}))
        self.nbformat = narr_dict.get("nbformat")
        self.nbformat_minor = narr_dict.get("nbformat_minor")
        self.cells = [
            Narrative.make_cell_from_dict(cell) for cell in narr_dict["cells"]
        ]
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

    def __str__(self):
        narr_obj = {
            "cells": [cell.to_dict() for cell in self.cells],
            "metadata": self.metadata.to_dict(),
            "nbformat": self.nbformat,
            "nbformat_minor": self.nbformat_minor
        }
        return json.dumps(narr_obj)

def is_narrative(obj_type: str) -> bool:
    return obj_type.startswith(NARRATIVE_TYPE)

