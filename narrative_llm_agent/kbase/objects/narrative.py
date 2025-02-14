import json
from typing import Any
from narrative_llm_agent.kbase.clients.execution_engine import JobState, ExecutionEngine
from narrative_llm_agent.util.app import map_inputs_from_job
from narrative_llm_agent.util.tool import convert_to_boolean
import time
import uuid


NARRATIVE_ID_KEY: str = "narrative"
NARRATIVE_NAME_KEY: str = "narrative_nice_name"
NARRATIVE_TYPE: str = "KBaseNarrative.Narrative"


class AppSpec:
    pass


class Cell:
    raw: dict
    cell_type: str
    source: str

    def __init__(self, cell_type: str, raw_cell: dict[str, any]) -> None:
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
    outputs: list[any]

    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("code", cell_dict)
        self.outputs = cell_dict.get("outputs", [])


class RawCell(Cell):
    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("raw", cell_dict)


class MarkdownCell(Cell):
    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("markdown", cell_dict)


class KBaseCell(CodeCell):
    def __init__(self, kb_cell_type: str, cell_dict: dict[str, any]) -> None:
        super().__init__(cell_dict)
        self.kb_cell_type = kb_cell_type

    def get_info_str(self):
        return f"kbase.{self.kb_cell_type}"


class AppCell(KBaseCell):
    app_spec: AppSpec
    app_id: str
    app_name: str
    job_state: JobState
    params: dict

    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("KBaseApp", cell_dict)
        app_info = cell_dict["metadata"]["kbase"].get("appCell", {})
        self.app_spec = app_info.get("app", {}).get("spec")
        self.app_id = self.app_spec["info"]["id"]
        self.app_name = self.app_spec["info"]["name"]
        self.job_state = None
        if "exec" in app_info and "jobState" in app_info["exec"]:
            self.job_state = JobState(app_info["exec"]["jobState"])
        self.params = app_info.get("params", {})

    def get_info_str(self):
        spec_info = self.raw["metadata"]["kbase"].get("appCell", {}).get("app")
        return f"method.{spec_info['id']}/{spec_info['gitCommitHash']}"


class BulkImportCell(KBaseCell):
    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("KBaseBulkImport", cell_dict)

    def get_info_str(self):
        return "kbase.bulk_import"


class DataCell(KBaseCell):
    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("KBaseData", cell_dict)

    def get_info_str(self):
        return "kbase.data_viewer"


class OutputCell(KBaseCell):
    def __init__(self, cell_dict: dict[str, any]) -> None:
        super().__init__("KBaseOutput", cell_dict)

    def get_info_str(self):
        return "kbase.app_output"


class NarrativeMetadata:
    creator: str
    data_dependencies: list[str]
    description: str
    format: str = "ipynb"
    name: str
    is_temporary: bool
    raw: dict[str, any]

    def __init__(self, narr_meta: dict[str, any]) -> None:
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
    cells: list[Cell]
    kbase_cells_by_id: dict[str, Cell]

    def __init__(self, narr_dict: dict[str, any]) -> None:
        if "cells" not in narr_dict:
            raise ValueError(
                "'cells' key not found, this might be a VERY old narrative. Please update it before continuing."
            )
        self.metadata = NarrativeMetadata(narr_dict.get("metadata", {}))
        self.nbformat = narr_dict.get("nbformat")
        self.nbformat_minor = narr_dict.get("nbformat_minor")
        self.cells = [
            Narrative.make_cell_from_dict(cell) for cell in narr_dict["cells"]
        ]
        self.kbase_cells_by_id = {}
        for cell in self.cells:
            cell_meta = cell.raw.get("metadata", {})
            if "kbase" in cell_meta and "attributes" in cell_meta["kbase"]:
                cell_id = cell_meta["kbase"]["attributes"].get("id")
                if cell_id is not None:
                    self.kbase_cells_by_id[cell_id] = cell
        self.raw = narr_dict

    @classmethod
    def make_cell_from_dict(cls, cell_dict: dict[str, any]) -> Cell:
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

    def _add_cell(self, cell: Cell) -> None:
        self.cells.append(cell)
        self.raw["cells"].append(cell.to_dict())
        cell_meta = cell.raw.get("metadata", {})
        if "kbase" in cell_meta and "attributes" in cell_meta["kbase"]:
            cell_id = cell_meta["kbase"]["attributes"].get("id")
            if cell_id is not None:
                self.kbase_cells_by_id[cell_id] = cell

    def add_markdown_cell(self, text: str) -> MarkdownCell:
        """
        Adds a markdown cell to the Narrative and returns it.
        """
        cell_dict = {
            "cell_type": "markdown",
            "source": text,
            "metadata": {"kbase": self._create_kbase_meta("markdown")}
        }
        new_cell = MarkdownCell(cell_dict)
        self._add_cell(new_cell)
        return new_cell

    def add_code_cell(self, source: str, outputs: list = []) -> CodeCell:
        """
        Adds a code cell to the Narrative and returns it.
        """
        cell_dict = self._create_cell_dict("code", "code", source, outputs=outputs)
        new_cell = CodeCell(cell_dict)
        self._add_cell(new_cell)
        return new_cell

    def add_app_cell(self, job_state: JobState, app_spec: dict) -> AppCell:
        """Adds an app cell to this narrative based on the job state and app spec.

        This unpacks information from the job state and app spec to build a new KBase
        app cell, which gets added to the bottom of the Narrative. The newly created
        cell gets returned.
        """
        cell_dict = self._create_cell_dict("code", "app", "")
        cell_dict["metadata"]["kbase"]["attributes"]["info"] = {
            "label": "more...",
            "url": "/#appcatalog/app/" + app_spec["info"]["id"] + "/release",
        }
        cell_dict["metadata"]["kbase"]["attributes"]["id"] = (
            job_state.job_input.narrative_cell_info.cell_id
        )
        cell_dict["metadata"]["kbase"]["attributes"]["subtitle"] = app_spec["info"][
            "subtitle"
        ]
        cell_dict["metadata"]["kbase"]["attributes"]["title"] = app_spec["info"]["name"]
        cell_dict["metadata"]["kbase"]["appCell"] = self._create_app_cell_meta(
            job_state, app_spec
        )
        new_cell = AppCell(cell_dict)
        self._add_cell(new_cell)
        return new_cell

    def _create_app_cell_meta(self, job_state: JobState, app_spec: dict) -> dict:
        """
        Creates the app cell metadata from info in the job state and app spec.
        """
        cell_job_state = self._get_cell_job_state(job_state)
        cell_job_state["status"] = (
            "queued"  # Force the Narrative Interface to update and redraw the cell
        )
        meta = {
            "app": {
                "gitCommitHash": app_spec["info"]["git_commit_hash"],
                "id": app_spec["info"]["id"],
                "version": app_spec["info"]["ver"],
                "tag": job_state.job_input.narrative_cell_info.app_version_tag,
                "spec": app_spec,
            },
            "exec": {
                "jobs": {"byId": {job_state.job_id: cell_job_state}},
                "jobState": cell_job_state,
                "launchState": {
                    "cell_id": job_state.job_input.narrative_cell_info.cell_id,
                    "run_id": job_state.job_input.narrative_cell_info.run_id,
                    "job_id": job_state.job_id,
                    "event": "launched_job",
                    "event_at": time.gmtime(),  # TODO make ISO time string
                },
            },
            "executionStats": {  # TODO: is this a service call? yes - catalog.get_exec_aggr_stats
                "full_app_id": app_spec["info"]["id"],
                "module_name": app_spec["info"]["module_name"],
            },
            "fsm": {
                "currentState": {
                    "mode": "processing",
                    "stage": "queued",  # TODO make this more fine-grained based on state, but hopefully YAGNI as the interface will just figure it out
                }
            },
            "paramDisplay": {},  # TODO
            "params": map_inputs_from_job(job_state.job_input.params, app_spec),
            "user-settings": {"showCodeInputArea": False},
        }
        return meta

    def _create_cell_dict(
        self, cell_type: str, kbase_cell_type: str, source: str, outputs: list = []
    ) -> dict[str, any]:
        return {
            "cell_type": cell_type,
            "source": source,
            "outputs": outputs,
            "metadata": {"kbase": self._create_kbase_meta(kbase_cell_type)},
            "execution_count": 0,
        }

    def _create_kbase_meta(self, kbase_cell_type: str) -> dict[str, any]:
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
            "cellState": {"toggleMinMax": "maximized"}
        }
        if kbase_cell_type not in ["markdown"]:
            meta["type"] = kbase_cell_type
        return meta

    def _get_cell_job_state(self, state: JobState) -> dict:
        cell_js = state.to_dict()
        if "job_input" in cell_js:
            del cell_js["job_input"]
        return cell_js

    def _get_new_cell_id(self) -> str:
        new_id = str(uuid.uuid4())
        while new_id in self.kbase_cells_by_id:
            new_id = str(uuid.uuid4())
        return new_id

    def get_current_state(
        self, ee_client: ExecutionEngine, as_json: bool = True
    ) -> dict[str, Any]:
        """
        Gets the current state of this narrative by the following means:
        1. Markdown and Code cells are left unchanged
        2. Various KBase cells are adjusted to not be quite as large. Metadata is reduced to the minimum to
           define what cell that is and what app (if any) exists in it.
        3. Any app cells get their job state (if any) looked up and updated.
        4. The narrative is then returned as a dictionary.
        """
        cell_states = []

        for cell in self.cells:
            if isinstance(cell, AppCell):
                reduced_app_cell = {
                    "app_id": cell.app_id,
                    "app_name": cell.app_name,
                    "app_params": cell.params,
                }
                if cell.job_state is not None:
                    job_id = cell.job_state.job_id
                    cur_state = ee_client.check_job(job_id)
                    reduced_app_cell["job_state"] = {
                        "job_id": job_id,
                        "status": cur_state.status,
                    }
                    if cur_state.error:
                        reduced_app_cell["job_state"]["error"] = cur_state.error
                    results = cur_state.job_output
                    if results:
                        if "results" in results:
                            results = results["results"]
                        reduced_app_cell["results"] = results
                cell_states.append(reduced_app_cell)

            elif isinstance(cell, OutputCell):
                # do output cell stuff later
                cell_states.append(cell.to_dict())
            else:
                cell_states.append(cell.to_dict())

        narr_dict = self._make_narrative_dict(cell_states, self.metadata.to_dict())
        if as_json:
            return json.dumps(narr_dict)
        return narr_dict

    def to_dict(self) -> dict[str, Any]:
        return self._make_narrative_dict(
            [cell.to_dict() for cell in self.cells], self.metadata.to_dict()
        )

    def _make_narrative_dict(
        self, cell_dicts: list[dict[str, Any]], meta_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "cells": cell_dicts,
            "metadata": meta_dict,
            "nbformat": self.nbformat,
            "nbformat_minor": self.nbformat_minor,
        }

    def get_cell_counts(self) -> dict[str, int]:
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
