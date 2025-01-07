from pathlib import Path

CATALOG_DIR: Path = Path(__file__).absolute().parent / "catalog_dump"
DEFAULT_EXT: str = "json"

def get_catalog_files(catalog_dir: Path=None, ext: str=None) -> list[Path]:
    if catalog_dir is None:
        catalog_dir = CATALOG_DIR
    if ext is None:
        ext = DEFAULT_EXT
    return [f for f in catalog_dir.iterdir() if f.is_file() and str(f).endswith("." + ext)]
