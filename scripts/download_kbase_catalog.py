from dataclasses import dataclass
from typing import Any
import requests
import json
import uuid
from argparse import ArgumentParser
from pathlib import Path
from bs4 import BeautifulSoup

ignore_categories = {"inactive", "upload", "viewers", "hidden"}


@dataclass
class DownloaderArgs:
    output_dir: Path
    catalog_url: str  # URL for the KBase Catalog service
    tag: str
    process: bool


def download_catalog(args: DownloaderArgs):
    nms_list_apps_params = {"tag": args.tag}
    nms_request = {
        "version": "1.1",
        "params": [nms_list_apps_params],
        "method": "NarrativeMethodStore.list_methods",
        "id": str(uuid.uuid4()),
    }
    list_apps_resp = requests.post(args.catalog_url, json=nms_request)
    list_apps_resp.raise_for_status()

    apps_list = list_apps_resp.json().get("result", [[]])[0]

    all_apps = {}
    get_info_list = []
    for app in apps_list:
        if set(app["categories"]) & ignore_categories:
            continue
        all_apps[app["id"]] = app
        get_info_list.append(app["id"])

    nms_get_apps_info_params = {"ids": get_info_list, "tag": args.tag}
    nms_request = {
        "version": "1.1",
        "id": str(uuid.uuid4()),
        "method": "NarrativeMethodStore.get_method_full_info",
        "params": [nms_get_apps_info_params],
    }

    get_full_info_resp = requests.post(args.catalog_url, json=nms_request)
    get_full_info_resp.raise_for_status()

    full_infos = get_full_info_resp.json().get("result", [[]])[0]
    for info in full_infos:
        all_apps[info["id"]].update(info)

    required_keys = [
        "id",
        "name",
        "subtitle",
        "tooltip",
        "description",
        "categories",
        "publications",
        "input_types",
        "output_types",
    ]
    for app_id, app in all_apps.items():
        dump_app = app
        # remove keys that are not needed
        for key in list(dump_app.keys()):
            if key not in required_keys:
                del dump_app[key]
        dump_app["categories"] = filter(lambda x: x != "active", dump_app["categories"])
        # write to file
        if args.process:
            process_and_save_text(app_id, dump_app, args.output_dir)
        else:
            save_json(app_id, dump_app, args.output_dir)


def save_json(app_id: str, data: dict[str, Any], output_dir: Path) -> None:
    file_name = output_dir / (app_id.replace("/", ".") + ".json")
    with open(file_name, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file)


def process_and_save_text(app_id: str, data: dict[str, Any], output_dir: Path) -> None:
    file_name = output_dir / (app_id.replace("/", ".") + ".txt")
    name = remove_html_tags(data["name"])
    subtitle = remove_html_tags(data["subtitle"])
    tooltip = remove_html_tags(data["tooltip"])
    description = remove_html_tags(data["description"])
    with open(file_name, "w", encoding="utf-8") as output_file:
        output_file.write("\n".join([name, subtitle, tooltip, description]))
        for key in ["categories", "input_types", "output_types"]:
            output_file.write(f"\n{key}: {','.join(data[key])}")
        output_file.write(f"\nid: {app_id}")


def remove_html_tags(html_text: str) -> str:
    # Parse the HTML content
    soup = BeautifulSoup(html_text, "html.parser")

    # Extract the text part only
    cleaned_text = soup.get_text(separator=" ", strip=True)

    return cleaned_text


def load_args() -> DownloaderArgs:
    parser = ArgumentParser(
        description="Download the KBase Catalog into a set of JSON files."
    )
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    parser.add_argument(
        "--env", "-e", default="prod", help="URL for the KBase Catalog service"
    )
    parser.add_argument(
        "--tag",
        "-t",
        default="release",
        help="app release tag. one of release, beta, dev",
    )
    parser.add_argument(
        "--process",
        "-p",
        action="store_true",
        help="process the results for adding to a RAG db. This removes the JSON structure, some fields, and stores the results as txt files",
    )
    args = parser.parse_args()
    env = args.env
    base_url = "kbase.us/services/narrative_method_store/rpc"
    env = "" if env == "prod" else env + "."
    catalog_url = f"https://{env}{base_url}"
    return DownloaderArgs(Path(args.output), catalog_url, args.tag, args.process)


if __name__ == "__main__":
    download_catalog(load_args())
