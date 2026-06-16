"""Export / restore a LangSmith dataset to/from a committed JSON snapshot.

Pick the dataset by name — `golden`, `pii`, or `hallucinations`:

    # recreate a dataset in LangSmith from its committed snapshot
    uv run python evals/dataset_snapshot.py restore golden
    uv run python evals/dataset_snapshot.py restore golden --reset    # overwrite if exists

    # pull the live dataset back down into its snapshot (e.g. after Engine
    # regenerates it, or after editing the golden examples in LangSmith)
    uv run python evals/dataset_snapshot.py export hallucinations

Each choice maps to a dataset name and a committed snapshot file (see
DATASETS below); override either with --name / --path. The snapshots are
committed to the repo so the datasets survive deletions and produce a
reproducible baseline for demo practice — no waiting on an Engine scan.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

load_dotenv(override=True)

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    path: Path


DATASETS = {
    "golden": DatasetConfig("banking-concierge-golden", HERE / "dataset_golden.json"),
    "hallucinations": DatasetConfig(
        "banking-concierge-hallucinations", HERE / "dataset_hallucinations.json"
    ),
    "pii": DatasetConfig("banking-concierge-pii", HERE / "dataset_pii.json"),
}

EXAMPLES = """\
examples:
  uv run python evals/dataset_snapshot.py restore golden --reset    # recreate from snapshot
  uv run python evals/dataset_snapshot.py restore hallucinations    # skip if it already exists
  uv run python evals/dataset_snapshot.py export pii                # pull live dataset into its snapshot
"""


class _ExamplesParser(argparse.ArgumentParser):
    """Show usage + examples instead of a terse usage line on error."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"\nerror: {message}\n\n{EXAMPLES}")
        raise SystemExit(2)


def export_dataset(name: str, path: Path) -> None:
    client = Client()
    ds = client.read_dataset(dataset_name=name)
    examples = list(client.list_examples(dataset_id=ds.id))

    payload = {
        "name": ds.name,
        "description": ds.description or "",
        "examples": [
            {
                "inputs": ex.inputs,
                "outputs": ex.outputs,
                "metadata": ex.metadata or {},
            }
            for ex in examples
        ],
    }

    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Exported {len(examples)} examples from {ds.name!r} to {path}")


def restore_dataset(path: Path, reset: bool) -> None:
    if not path.is_file():
        raise SystemExit(
            f"Snapshot not found at {path}. Run `dataset_snapshot.py export` first."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    name = payload["name"]
    description = payload.get("description") or ""
    examples = payload.get("examples", [])

    client = Client()
    existing = list(client.list_datasets(dataset_name=name))
    if existing:
        if not reset:
            print(
                f"Dataset {name!r} already exists in LangSmith. "
                "Pass --reset to delete and recreate it."
            )
            return
        print(f"Deleting existing dataset {name!r}...")
        client.delete_dataset(dataset_name=name)

    ds = client.create_dataset(dataset_name=name, description=description)
    print(f"Created dataset {ds.name} ({ds.id})")

    if not examples:
        print("Snapshot has no examples; dataset created empty.")
        return

    client.create_examples(
        dataset_id=ds.id,
        examples=[
            {
                "inputs": ex.get("inputs", {}),
                "outputs": ex.get("outputs", {}),
                "metadata": ex.get("metadata", {}) or {},
            }
            for ex in examples
        ],
    )
    print(f"Restored {len(examples)} examples.")


def main() -> None:
    parser = _ExamplesParser(
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "mode",
        choices=("export", "restore"),
        help="export: pull from LangSmith into the snapshot. restore: push snapshot back.",
    )
    parser.add_argument(
        "dataset_choice",
        choices=sorted(DATASETS),
        help="Which dataset to act on.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Override the dataset name in LangSmith for the chosen dataset.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override the snapshot file path for the chosen dataset.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="(restore only) Delete and recreate the dataset if it already exists.",
    )
    args = parser.parse_args()

    config = DATASETS[args.dataset_choice]
    name = args.name or config.name
    path = args.path or config.path

    if args.mode == "export":
        if args.reset:
            print("--reset is ignored in export mode.", file=sys.stderr)
        export_dataset(name, path)
    else:
        restore_dataset(path, args.reset)


if __name__ == "__main__":
    main()
