"""Run an offline experiment against an Engine-generated dataset.

Targets the dataset LangSmith Engine produced from failing prod traces
of the "Agent fabricates specific banking facts not grounded in the
knowledge base" issue. The `hallucination_evaluator` scores whether the
response is grounded in retrieval so the LangSmith experiment view shows
the hallucination rate.

Local baseline (before opening a PR with Engine's proposed fix):

    uv run python evals/run_engine_experiment.py

The post-fix run is normally produced by .github/workflows/evals-on-pr.yml
when a PR is opened — the workflow runs this script against the PR's
checked-out code, so we get a "fix applied" experiment without
redeploying the agent.

Metadata can be threaded into the LangSmith experiment with repeatable
--metadata key=value flags (the CI workflow uses this for pr_number /
commit_sha / branch).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
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
)
from langsmith import Client, aevaluate  # noqa: E402

DEFAULT_DATASET = "banking-concierge-hallucinations"

EVALUATOR_REGISTRY = {
    "hallucination": hallucination_evaluator,
    "pii_leak_rate": pii_leak_rate_evaluator,
}
DEFAULT_EVALUATORS = ["hallucination"]


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


def _looks_like_uuid(s: str) -> bool:
    return len(s) == 36 and s.count("-") == 4


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=(
            "Dataset name or ID. Default is the Engine-generated "
            f"'{DEFAULT_DATASET}' dataset."
        ),
    )
    parser.add_argument("--experiment-prefix", default="banking-concierge-hallucinations")
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
            "Evaluator to attach (repeatable). Defaults to 'hallucination'. "
            "Pass --evaluator pii_leak_rate for the PII-leak dataset."
        ),
    )
    args = parser.parse_args()
    evaluators = args.evaluator or DEFAULT_EVALUATORS

    asyncio.run(
        run(
            args.dataset,
            args.experiment_prefix,
            args.max_concurrency,
            _parse_metadata(args.metadata),
            evaluators,
        )
    )


if __name__ == "__main__":
    main()
