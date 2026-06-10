# Meridian National Customer Service Concierge

A demo personal-banking customer service agent built to show off **LangSmith Engine**. It's a multi-turn chat agent built on a custom LangGraph `StateGraph` that uses a synthetic Meridian National knowledge base plus mocked customer-data tools, and is deployable to LangSmith Cloud.

The agent is intentionally a bit imperfect: the system prompt is under-specified and a few tools have rough edges, so when you run the load generator against it you get a healthy mix of clean traces, hallucinations, broken tool calls, scope-drifted answers, and over-retrieval loops. Engine clusters those into issues during the demo.

The two headline bugs live on **two different fix surfaces**, so the demo shows both ways Engine recommends a fix:

| Bug | Lives in | Effect | Engine fixes it by |
|---|---|---|---|
| "Answer rate questions from memory" instruction | **LangSmith Context Hub** (`banking-concierge-agent` / `AGENTS.md`) | ~40% ungrounded APY/APR answers | **Editing `AGENTS.md` in the Context Hub UI** — no code redeploy |
| `account_lookup` returns unmasked PII | `src/concierge/tools.py` | SSN / card / CVV read back verbatim | **Opening a GitHub PR** against the connected repo |

The agent's instructions are stored in Context Hub as a versioned `AGENTS.md` and pulled at runtime by `src/concierge/context.py:get_prompt()`. The repo keeps only that breadcrumb so Engine knows the prompt lives in the hub. Context Hub also holds a small library of show-only `SKILL.md` repos (the agent doesn't load them) to illustrate what a skills library looks like alongside the agent.

## What's in here

```
src/concierge/
  graph.py         StateGraph -> agent (LLM) <-> ToolNode
  app.py           FastAPI custom routes (mounts the React UI at /concierge/)
  state.py         MessagesState + retrieval_calls counter
  context.py       Pulls the system prompt (AGENTS.md) from LangSmith Context Hub at runtime
  context_hub.py   Seeds the hub AGENTS.md + show-only SKILL.md repos
  prompts.py       Under-specified system prompt — seed pushed to the hub + offline fallback
  tools.py         search_banking_docs + 4 mocked banking tools
  retrieval.py     In-memory vector store over kb/*.md
  mock_data.py     Fake customers, transactions, branches
  kb/              ~20 synthetic banking FAQ markdown docs
frontend/
  src/             React + assistant-ui chat client (Vite + Tailwind v4)
scripts/
  load_generation.py     Runs ~150 mixed conversations against the agent
  setup_context_hub.py   One-shot: seeds the hub with AGENTS.md + demo skills
evals/
  golden_dataset.py         Creates the 7-example banking-concierge-golden dataset
  evaluators.py             LLM judges (hallucination, trajectory, assertions) + pii_leak_rate regex check
  run_experiment.py         aevaluate(...) runner for the golden dataset
  run_engine_experiment.py  Runner for the Engine assertion datasets (hallucinations / pii)
  engine_dataset.py         Snapshots the Engine datasets to/from committed JSON (export / restore)
  engine_dataset.json       Committed snapshot of banking-concierge-hallucinations
  engine_dataset_pii.json   Committed snapshot of banking-concierge-pii
langgraph.json       Deployment manifest (graphs + http.app) for LangSmith Cloud
```

## Setup

Prerequisites: Python 3.13, [`uv`](https://docs.astral.sh/uv/), and a LangSmith account (Plus or above to deploy).

### Fork the repo and use your own workspace (do this first)

This demo connects LangSmith Engine to a GitHub repo, lets Engine open a PR against it, and creates datasets, a Context Hub repo, a tracing project, and a deployment all named `banking-concierge-*`. To avoid disturbing other people's demos:

- **Fork [`langchain-samples/banking-concierge`](https://github.com/langchain-samples/banking-concierge)** into your own GitHub account or org and work from the fork. You'll connect Engine to **your fork**, so its auto-generated PII-fix PR lands on your fork instead of the shared upstream.
- **Use your own LangSmith workspace.** The dataset names (`banking-concierge-golden` / `-hallucinations` / `-pii`), the Context Hub repo (`banking-concierge-agent`), the tracing project, and the deployment are all named by convention and will collide if several people run the demo in one shared workspace. Point `.env`'s `LANGSMITH_WORKSPACE_ID` (and your API keys) at your own workspace.

Set the CI secrets (`OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_WORKSPACE_ID`) on your fork too — see [Repeatable demo via GitHub Actions](#repeatable-demo-via-github-actions).

```bash
uv sync
cp .env.example .env   # then point LANGSMITH_WORKSPACE_ID / API keys at your own workspace
```

Required environment variables (see `.env.example`):

| Var | Purpose |
|---|---|
| `OPENAI_API_KEY` | Agent + judge model calls |
| `LANGSMITH_API_KEY` | Tracing, datasets, experiments, deployment |
| `LANGSMITH_TRACING` | `"true"` to send traces |
| `LANGSMITH_PROJECT` | Tracing project for ad-hoc and loadgen runs |
| `LANGSMITH_WORKSPACE_ID` | Workspace (tenant) the Context Hub repo is seeded into |
| `CONCIERGE_MODEL` | _(optional)_ override the agent's chat model |
| `LANGGRAPH_DEPLOYMENT_URL` | _(optional)_ deployment URL for `load_generation.py --mode remote` |

### Seed Context Hub (one-time)

The agent pulls its system prompt from LangSmith Context Hub, so seed the hub before the first run:

```bash
uv run python -m scripts.setup_context_hub
```

This creates the `banking-concierge-agent` agent repo (with the buggy `AGENTS.md`) and a few show-only `banking-concierge-*` skill repos. Until it's run, `get_prompt()` falls back to the seed in `prompts.py`, so the agent still works — but the "fix in Context Hub" demo beat needs the hub repo to exist.

## Run locally

```bash
# one-time: build the custom chat UI (only needed for /concierge/, not for Studio)
npm --prefix frontend install
npm --prefix frontend run build

# start the agent server + custom routes
uv run langgraph dev
```

`langgraph dev` serves two separate UIs. Paste the full URL into your browser:

- **`http://localhost:2024/concierge/`** — the project's custom React chat UI (the main demo UI), served by `src/concierge/app.py` from `frontend/dist/`. This is what `npm run build` produces; until you build it, the page returns a 503 with a "run npm build" hint.
- **`http://localhost:2024/app/`** — LangGraph Studio, the built-in debugger. Works with no frontend build.

`http://localhost:2024/` (the bare root) just redirects to `/concierge/`.

**Iterating on the frontend?** Rebuilding on every change is slow, so run the Vite dev server in a second terminal instead:

```bash
npm --prefix frontend run dev   # hot-reloading UI on http://localhost:5173
```

Open `http://localhost:5173` (not `:2024`) — it live-reloads your React edits without a rebuild. The app still needs the agent backend, whose API lives on `:2024`, so Vite is configured (`frontend/vite.config.ts`) to **proxy** the agent endpoints (`/threads`, `/runs`, `/assistants`, `/info`) through to `localhost:2024`. Keep `uv run langgraph dev` running on `:2024` for that to work.

## Generate load (so Engine has data to cluster)

```bash
# in-process against the local compiled graph
uv run python scripts/load_generation.py --mode local --n 150

# against a deployed LangSmith assistant
uv run python scripts/load_generation.py --mode remote --n 150 \
    --url $LANGGRAPH_DEPLOYMENT_URL

# burst PII categories — seeds gateway redaction events fast
uv run python scripts/load_generation.py --mode remote --n 50 --only pii
```

The PII pool covers two distinct paths:

- `pii_leak` (and `pii_leak_multiturn`) — user *asks* the agent to read back PII; the leak appears in the agent's response. Exercises the response-side redaction.
- `pii_in_user_input` (and `_multiturn`) — user *includes* real-looking PII in their message (SSNs, full card numbers + CVV + exp, names/ages/places). Most reliable trigger for incoming-message redaction policies, because the regex/ML matcher sees the values in the human turn before any tool runs. When redaction fires, the model receives placeholders like `SAFE_TO_USE:US_SSN_xxxx` instead of `552-19-4488`, which often causes the agent to misuse the placeholder downstream — useful as a secondary signal Engine can cluster on. (This `SAFE_TO_USE:*` placeholder path only appears when the LangSmith LLM gateway is enabled. It's **off by default** — `BASE_URL` is unset — so a normal loadgen run won't produce placeholders unless you opt in; see the gateway section in `DEMO.md`.)

Each run is tagged with `loadgen` and `category:<intent>` so you can verify Engine's clusters match the planted error modes (`hallucination_bait`, `broken_tool`, `out_of_scope`, `excessive_retrieval`, `pii_leak`).

## Create the evaluation datasets

Create these before running any experiment below — they're built deterministically from the repo, so you do **not** have to wait for an Engine scan. The golden dataset is built from code; the two Engine datasets are restored from committed JSON **snapshots** (`evals/engine_dataset.json` → `banking-concierge-hallucinations`, `evals/engine_dataset_pii.json` → `banking-concierge-pii`). `engine_dataset.py` is a small repo-local script wrapping the LangSmith SDK (not a built-in command); `restore` reads the dataset name from inside the snapshot, so it picks the target purely by `--path`.

```bash
# golden (hand-authored in evals/golden_dataset.py)
uv run python evals/golden_dataset.py --reset

# Engine datasets, restored from committed snapshots (--reset deletes + rebuilds if present)
uv run python evals/engine_dataset.py restore --reset                                         # hallucinations
uv run python evals/engine_dataset.py restore --reset --path evals/engine_dataset_pii.json    # pii
```

The committed snapshots are the **source of truth for setup**, so a rehearsal or CI run produces identical examples every time — no waiting on a ~20-minute Engine scan.

## Run the offline experiment (golden dataset)

```bash
uv run python evals/run_experiment.py
```

This runs `aevaluate` over `banking-concierge-golden`, attaching two LLM-as-judge scores to each run:

- `hallucination` — a local LLM-as-judge (no openevals dependency), given the assistant's final answer plus the retrieved/tool-output context. Scores 1.0 when it detects an ungrounded claim and 0.0 when grounded, so the aggregate reads as a hallucination rate (higher is worse).
- `trajectory_accuracy` — a local LLM-as-judge (no agentevals dependency) that grades the agent's actual tool-call trajectory against a reference synthesized from the example's `expected_tools`.

## Engine-issue regression demo

When Engine promotes a failing prod trace into a dataset, it stores per-claim **assertions** instead of a single reference answer. `evals/run_engine_experiment.py` — a separate runner from the `run_experiment.py` golden-dataset runner above; this one grades the Engine-generated assertion datasets — targets one such dataset (the "agent fabricates specific banking facts" hallucinations dataset by default) and runs two evaluators against it:

- `assertions_evaluator` — emits one feedback row per assertion (`must_not_state_2pm_pacific_for_domestic_wire`, `must_ground_cutoff_in_retrieval`, etc.) so the LangSmith UI shows per-claim pass/fail.
- `hallucination_evaluator` — same aggregate hallucination score used elsewhere, for a single headline number.

Run the baseline for **both** headline issues before applying Engine's fixes:

```bash
# hallucinations dataset — uses the defaults (banking-concierge-hallucinations
# dataset + the assertions and hallucination evaluators), so no flags needed
uv run python evals/run_engine_experiment.py

# pii dataset — needs its own dataset, experiment prefix, and evaluators
# (the defaults are hallucination-specific; repeating --evaluator replaces them)
uv run python evals/run_engine_experiment.py \
  --dataset banking-concierge-pii \
  --experiment-prefix banking-concierge-pii-leak \
  --evaluator assertions --evaluator pii_leak_rate
```

Then apply Engine's fix for each (Context Hub edit for the hallucination, GitHub PR for the PII leak), redeploy, and re-run the **same two commands** — each appears as a new experiment on its dataset. Open the before/after pair side-by-side in LangSmith → Experiments to watch the per-assertion columns flip FAIL → PASS.

### Repeatable demo via GitHub Actions

For a repeatable on-stage demo where you don't want to redeploy the agent, `.github/workflows/evals-on-pr.yml` runs `run_engine_experiment.py` on every pull request. The workflow is a strategy matrix over every Engine-generated dataset, so each PR fires one parallel job per dataset (currently `banking-concierge-hallucinations` and `banking-concierge-pii`) and posts a separate PR comment per dataset linking to that experiment. Experiments are tagged with `pr_number`, `commit_sha`, `branch`, `ci_run_id`, and `engine_issue=<alias>`, and prefixed `<issue>-pr-<N>-<sha>` so they're easy to find later.

Why run both on every PR: when a PR fixes one issue, the other dataset's result lets you see whether the fix caused unintended cross-impact (improvement, neutral, or regression on the other issue). To add a new dataset, just append an entry to `strategy.matrix.include` in the workflow.

Demo flow:

1. Run the baseline locally on `main` once: `uv run python evals/run_engine_experiment.py`
2. Engine opens a PR with the proposed fix (or you open one with the fix applied).
3. The workflow fires automatically, runs the experiment against the PR's code, and comments the LangSmith link on the PR.
4. In LangSmith → Datasets → `banking-concierge-hallucinations` → Compare, pick the baseline experiment and the PR experiment to show per-assertion improvements without ever shipping the fix.

Required GitHub configuration:

- Secrets: `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_WORKSPACE_ID`.
- Variables (optional): `LANGSMITH_PROJECT`, `BASE_URL` (gateway), `CONCIERGE_MODEL`.

## Deploy to LangSmith Cloud

```bash
# Build the frontend first — its dist/ is what the deployment serves
npm --prefix frontend install
npm --prefix frontend run build

uv tool install langgraph-cli
uv run langgraph deploy
```

The deployment manifest (`langgraph.json`) registers one assistant `agent` (`src/concierge/graph.py:graph`) and one custom HTTP app (`src/concierge/app.py:app`) that mounts the built React UI at `/concierge/`.

LangSmith Cloud deployments protect the default `/threads`, `/runs`, and `/assistants` endpoints with the workspace's API key. The React client supports two ways to pass the key:

- **URL parameter (demo)**: open `https://<deployment>.us.langgraph.app/concierge/?api_key=lsv2_pt_...` once. The frontend promotes the key into `localStorage` and strips it from the visible URL, so subsequent visits don't need it.
- **Manual**: `localStorage.setItem("concierge:apiKey", "lsv2_pt_...")` from the browser console.

The key is sent as `X-Api-Key` on every SDK call. It is client-side credentials — fine for a stage demo, rotate after.

Once deployed:

1. In LangSmith, open the tracing project and **enable Engine**.
2. Set priorities to **Tool Call Failures**, **Hallucinations**, **Out-of-Scope**, and a custom phrase for the PII leak (e.g. "agent reads back customer SSN, card number, CVV, phone, or email in plain text"). Hallucinations and the PII leak are the two you'll fix on stage; the rest surface the other planted error modes. Without explicit priorities, Engine ranks issues against a default rubric that may not surface what you want.
3. **Connect your fork** so Engine's "Open PR" works (required for the PII fix beat).
4. Run `load_generation.py --mode remote --url <deployment-url>` to populate traces.
5. Wait up to ~20 minutes for the first Engine scan.
6. In the Engine tab you should see distinct clusters matching the planted error modes, each with a proposed fix, a suggested evaluator, and offline examples you can add to a dataset. The hallucination cluster's fix is applied in the **Context Hub** (`AGENTS.md`); the PII cluster's fix is a **GitHub PR** against `tools.py` in your fork.

## Demo walkthrough

1. Show Studio: `uv run langgraph dev`, send a few realistic banking questions.
2. Run the load generator: 150 mixed conversations, tagged by category.
3. In LangSmith, filter traces by tag to show the planted error modes are present.
4. Open the **Engine** tab; show the clusters Engine produced, the proposed fixes, and the auto-generated dataset examples.
5. Show the **two fix surfaces**: fix the hallucination by editing `AGENTS.md` in the **Context Hub** (no redeploy — the agent pulls the new version), and let Engine open a **GitHub PR** for the PII leak in `tools.py`. Optionally open the Context Hub to show the show-only skills library alongside the agent.
6. Show the golden dataset and the offline experiment in **Datasets & Experiments** — the two LLM-as-judge scores are visible per run.
7. Close the loop: open one Engine-proposed evaluator, deploy it, and explain that future regressions will be auto-detected against this exact dataset.
