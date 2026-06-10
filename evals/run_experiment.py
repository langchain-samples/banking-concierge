"""Run the offline evaluation experiment against the golden dataset.

    uv run python evals/run_experiment.py

Prints the LangSmith experiment URL on completion.
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
from evaluators import hallucination_evaluator, trajectory_evaluator  # noqa: E402
from langsmith import aevaluate  # noqa: E402


async def target(inputs: dict) -> dict:
    return await graph.ainvoke(inputs)


async def run(dataset: str, experiment_prefix: str, max_concurrency: int) -> None:
    results = await aevaluate(
        target,
        data=dataset,
        evaluators=[hallucination_evaluator, trajectory_evaluator],
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
    )
    print()
    print(f"Experiment: {results.experiment_name}")
    if getattr(results, "_manager", None) and getattr(results._manager, "experiment", None):
        exp = results._manager.experiment
        print(f"Experiment URL: {getattr(exp, 'url', '(see LangSmith UI)')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="banking-concierge-golden")
    parser.add_argument("--experiment-prefix", default="banking-concierge")
    parser.add_argument("--max-concurrency", type=int, default=4)
    args = parser.parse_args()

    asyncio.run(run(args.dataset, args.experiment_prefix, args.max_concurrency))


if __name__ == "__main__":
    main()
