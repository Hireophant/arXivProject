"""Execute the preparation notebook with explicit local input/output paths."""
import argparse
import json
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", default="Danh2")
    parser.add_argument("--max-papers", type=int, default=100)
    parser.add_argument("--retry-blocked", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    notebook = nbformat.read(repo / "src/notebooks/milestone2_prepare.ipynb", as_version=4)
    parameters = (
        "from pathlib import Path\n"
        f"SOURCE_PATH=Path({str(args.source.resolve())!r})\n"
        f"PREPARATION_DIR=Path({str(args.output.resolve())!r})\n"
        f"DATASET_NAME={args.dataset!r}\n"
        f"PROJECT_DIR=Path({str(repo)!r})\n"
        "REPOSITORY_URL='unused'\nREPOSITORY_BRANCH='master'\n"
        "CLONE_IF_NEEDED=False\nSHOW_PROGRESS_EVERY=10\n"
        f"MAX_PAPERS_PER_RUN={args.max_papers!r}\nRETRY_BLOCKED={args.retry_blocked!r}\n"
    )
    for cell in notebook.cells:
        if "parameters" in cell.get("metadata", {}).get("tags", []):
            cell.source = parameters
    args.output.mkdir(parents=True, exist_ok=True)
    NotebookClient(notebook, timeout=1800, kernel_name="python3",
                   resources={"metadata": {"path": str(repo)}}).execute()
    nbformat.write(notebook, args.output / "notebook-executed.ipynb")
    summary = json.loads((args.output / "raw_m1" / args.dataset / "preparation.json").read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("All preparation notebook cells executed. Source/Drive coverage follows the summary above.")
    if summary["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
