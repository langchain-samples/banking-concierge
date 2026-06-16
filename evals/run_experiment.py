"""Run an offline evaluation experiment against one of the project datasets.

Pick the dataset by name (required) — `golden`, `pii`, or `hallucinations`:

    uv run python evals/run_experiment.py golden          # 7-example regression suite
    uv run python evals/run_experiment.py hallucinations  # Engine "fabricated facts" dataset
    uv run python evals/run_experiment.py pii             # Engine PII-leak dataset

Each choice selects a sensible default dataset name, evaluator set, and
experiment prefix (see DATASETS below). Any default can be overridden with
--dataset / --evaluator / --experiment-prefix.

The `hallucinations` and `pii` datasets are produced by LangSmith Engine from
failing prod traces, so their experiments double as regression suites for those
issues. The post-fix run is normally produced by .github/workflows/evals-on-pr.yml
when a PR is opened — the workflow runs this script against the PR's checked-out
code, so we get a "fix applied" experiment without redeploying the agent.

Metadata can be threaded into the LangSmith experiment with repeatable
--metadata key=value flags (the CI workflow uses this for pr_number /
commit_sha / branch).

Prints CI-parseable lines (EXPERIMENT_NAME=, EXPERIMENT_URL=, ...) on completion.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from concierge.graph import graph  # noqa: E402
from evaluators import (  # noqa: E402
    hallucination_evaluator,
    pii_leak_rate_evaluator,
    trajectory_evaluator,
)
from langsmith import Client, aevaluate  # noqa: E402

EVALUATOR_REGISTRY = {
    "hallucination": hallucination_evaluator,
    "trajectory": trajectory_evaluator,
    "pii_leak_rate": pii_leak_rate_evaluator,
}


@dataclass(frozen=True)
class DatasetConfig:
    dataset: str
    evaluators: list[str]
    experiment_prefix: str


DATASETS = {
    "golden": DatasetConfig(
        dataset="banking-concierge-golden",
        evaluators=["hallucination", "trajectory"],
        experiment_prefix="banking-concierge",
    ),
    "hallucinations": DatasetConfig(
        dataset="banking-concierge-hallucinations",
        evaluators=["hallucination"],
        experiment_prefix="banking-concierge-hallucinations",
    ),
    "pii": DatasetConfig(
        dataset="banking-concierge-pii",
        evaluators=["pii_leak_rate"],
        experiment_prefix="banking-concierge-pii-leak",
    ),
}


EXAMPLES = """\
examples:
  uv run python evals/run_experiment.py golden          # 7-example golden suite
  uv run python evals/run_experiment.py hallucinations  # Engine "fabricated facts" dataset
  uv run python evals/run_experiment.py pii             # Engine PII-leak dataset
"""


class _ExamplesParser(argparse.ArgumentParser):
    """Show full help (including examples) instead of a terse usage line on error."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"\nerror: {message}\n\n{EXAMPLES}")
        raise SystemExit(2)


async def target(inputs: dict) -> dict:
    return await graph.ainvoke(inputs)


def _parse_metadata(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--metadata expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _looks_like_uuid(s: str) -> bool:
    return len(s) == 36 and s.count("-") == 4


def _print_experiment_link(dataset: str, experiment_name: str) -> None:
    """Print CI-parseable lines (EXPERIMENT_NAME=, EXPERIMENT_URL=, etc.).

    The GitHub workflow greps stdout for these so it can post a useful
    PR comment.
    """
    import os

    client = Client()
    try:
        if _looks_like_uuid(dataset):
            ds = client.read_dataset(dataset_id=dataset)
        else:
            ds = client.read_dataset(dataset_name=dataset)
    except Exception as exc:  # noqa: BLE001
        print(f"EXPERIMENT_NAME={experiment_name}")
        print(f"# Could not resolve dataset URL: {exc}")
        return

    # `selectedSessions` expects experiment UUIDs which we don't have here,
    # so just link to the dataset's compare page — the experiment name will
    # be one row in the picker.
    workspace_id = os.getenv("LANGSMITH_WORKSPACE_ID", "").strip()
    base = "https://smith.langchain.com"
    if workspace_id:
        url = f"{base}/o/{workspace_id}/datasets/{ds.id}/compare"
    else:
        url = f"{base}/datasets/{ds.id}/compare"

    print(f"EXPERIMENT_NAME={experiment_name}")
    print(f"EXPERIMENT_URL={url}")
    print(f"DATASET_NAME={dataset}")
    print(f"DATASET_ID={ds.id}")


async def run(
    dataset: str,
    experiment_prefix: str,
    max_concurrency: int,
    metadata: dict[str, str],
    evaluators: list[str],
) -> None:
    evaluator_fns = [EVALUATOR_REGISTRY[name] for name in evaluators]
    results = await aevaluate(
        target,
        data=dataset,
        evaluators=evaluator_fns,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        metadata=metadata or None,
    )
    print()
    _print_experiment_link(dataset, results.experiment_name)


def main() -> None:
    parser = _ExamplesParser(
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "dataset_choice",
        choices=sorted(DATASETS),
        help="Which dataset to run against.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Override the dataset name or ID for the chosen dataset.",
    )
    parser.add_argument(
        "--experiment-prefix",
        default=None,
        help="Override the experiment prefix for the chosen dataset.",
    )
    parser.add_argument("--max-concurrency", type=int, default=4)
    parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Attach metadata to the LangSmith experiment. Repeatable. "
            "The CI workflow injects pr_number, commit_sha, and branch."
        ),
    )
    parser.add_argument(
        "--evaluator",
        action="append",
        default=None,
        choices=sorted(EVALUATOR_REGISTRY),
        help=(
            "Evaluator to attach (repeatable). Defaults to the chosen "
            "dataset's evaluators."
        ),
    )
    args = parser.parse_args()

    config = DATASETS[args.dataset_choice]
    dataset = args.dataset or config.dataset
    experiment_prefix = args.experiment_prefix or config.experiment_prefix
    evaluators = args.evaluator or config.evaluators

    asyncio.run(
        run(
            dataset,
            experiment_prefix,
            args.max_concurrency,
            _parse_metadata(args.metadata),
            evaluators,
        )
    )


if __name__ == "__main__":
    main()
