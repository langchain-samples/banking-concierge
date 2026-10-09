"""Deploy the committed HEAD to LangSmith Cloud, stamped with its git SHA.

Refuses to deploy a dirty working tree (so the deployed code always matches a
commit), then writes ``LANGSMITH_REVISION_ID=<git rev-parse HEAD>`` into
``.env`` — the file ``langgraph deploy`` reads deployment env vars from — so
every trace carries the deployed commit as ``revision_id`` metadata.

    uv run python -m scripts.deploy [extra `langgraph deploy` args]
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
REVISION_KEY = "LANGSMITH_REVISION_ID"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    if _git("status", "--porcelain"):
        print(
            "Error: working tree has uncommitted changes; commit them before deploying."
        )
        sys.exit(1)

    revision = _git("rev-parse", "HEAD")
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not line.startswith(f"{REVISION_KEY}=")]
    lines.append(f'{REVISION_KEY}="{revision}"')
    ENV_FILE.write_text("\n".join(lines) + "\n")
    print(f"Deploying {revision}", flush=True)

    sys.exit(
        subprocess.run(
            ["langgraph", "deploy", *sys.argv[1:]], check=False, cwd=ROOT
        ).returncode
    )


if __name__ == "__main__":
    main()
