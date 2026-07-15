from __future__ import annotations

import argparse
import json
from pathlib import Path


def clear_notebook(path: Path) -> bool:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("execution_count") is not None:
            cell["execution_count"] = None
            changed = True
        if cell.get("outputs"):
            cell["outputs"] = []
            changed = True

    metadata = notebook.get("metadata", {})
    kernelspec = metadata.get("kernelspec")
    if isinstance(kernelspec, dict) and kernelspec.get("name") != "python3":
        kernelspec.update({"display_name": "Python 3", "language": "python", "name": "python3"})
        changed = True

    if changed:
        path.write_text(
            json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear stored outputs from Jupyter notebooks.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.paths:
        status = "cleared" if clear_notebook(path) else "unchanged"
        print(f"{status}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
