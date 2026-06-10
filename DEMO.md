# Demo runbook

Rehearsal-ready clean-slate procedure for the LangSmith Engine demo. Read top to bottom before tearing anything down. For what the demo *is*, initial setup, and how the pieces fit together, see the [README](README.md) — this file is the day-of operational runbook, not a concepts doc.

## 0. Before you delete anything

A safety pass that takes under five minutes.

- [ ] **Confirm the dataset snapshots are committed.** They survive any LangSmith wipe.
  ```bash
  jq '.name, (.examples | length)' evals/engine_dataset.json evals/engine_dataset_pii.json
  # expect: banking-concierge-hallucinations / 7 ; banking-concierge-pii / 16
  ```
- [ ] **Screenshot the current Engine issue pages** (diagnosis text, proposed fix, suggested evaluator, "Add offline examples" dialog). Engine regenerates this text per scan and may phrase things differently on the next pass — useful as a backup for the slides.
- [ ] **Screenshot the Engine-generated PRs** (`issues-agent/<uuid>` branches). The PR URLs and inline review comments will 404 once the run-level traces they cite are gone.
- [ ] **Screenshot the CI PR comments** with the experiment links — links will break after the experiments are deleted.
- [ ] **Note current Engine settings**: which priorities are enabled, GitHub-repo connection on/off, scan cadence, webhooks. You'll re-enter these.

## 1. Safe to delete in LangSmith

- All traces in the tracing project (default: `banking-concierge`).
- Datasets: `banking-concierge-golden`, `banking-concierge-hallucinations`, `banking-concierge-pii`.
- Every experiment under those datasets.
- Every Engine-detected issue on the project.
- Annotation queues if any.

## 2. Do NOT touch

- **Workspace settings**: Provider Secrets (the OpenAI key stored in the gateway), the PII redaction / secrets redaction policy. They're workspace-scoped and survive project deletion.
- **Context Hub repos** (`banking-concierge-agent` + the `banking-concierge-*` demo skills). They're workspace-scoped, survive a tracing-project wipe, and the agent pulls `AGENTS.md` from here at runtime. If you delete them, re-seed with `uv run python -m scripts.setup_context_hub` (the agent falls back to `prompts.py` until you do).
- **The Cloud deployment** (`banking-concierge-…us.langgraph.app`). Deployments are independent of tracing projects/datasets. Deleting them costs you a fresh deploy and a new URL.
- **`.env`** — all credentials live there.
- **The repo** — source of truth for everything reproducible.
- **GitHub repo + secrets** (`OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_WORKSPACE_ID`) — CI depends on them.

## 3. Rebuild from scratch

Run these in order from the project root.

### 3a. Make sure the deployment is on `main`

The baseline carries **two pre-fix bugs on two different fix surfaces** — that's exactly what we want, and it's the point of the demo: Engine recommends a fix in whichever surface the bug lives in.

- **Hallucination — lives in LangSmith Context Hub (`AGENTS.md`).** The system prompt is seeded into Context Hub (see 3a-bis) with a "Tone and confidence" paragraph that *actively* pushes the agent to give specific numbers (APYs, fees, cutoffs, basis points) from training-time knowledge when retrieval misses, and bans hedge phrases like "I'm not sure" or "I couldn't find that". This is stronger than just "loose" — gpt-4o-mini hedges by default, and a merely permissive prompt didn't produce enough hallucinations for Engine to cluster on. **The fix is applied by editing `AGENTS.md` in the Context Hub UI — no code redeploy.** `src/concierge/prompts.py` holds the same text only as the seed + offline fallback.
- **PII leak — lives in `src/concierge/tools.py`.** `account_lookup` returns the full customer record verbatim (SSN, full card number, CVV, phone, email). **The fix is a GitHub PR** that masks these at the tool boundary (`ssn_last4`, card `last4` only, `email_masked`).

Combined effect: the deployed baseline confidently invents specific banking numbers when asked off-KB, and reads PII back in plain text when asked. Both are reliable failure clusters.

### 3a-bis. Seed Context Hub

The agent pulls its system prompt (`AGENTS.md`) from Context Hub at runtime. Seed it once before deploying:

```bash
uv run python -m scripts.setup_context_hub
```

This creates the `banking-concierge-agent` agent repo (buggy `AGENTS.md`) plus a few show-only `banking-concierge-*` skill repos. Re-run after a `--full` Context Hub wipe; harmless to re-run (idempotent).

```bash
git checkout main
git pull
uv run langgraph deploy
```

If you can skip the redeploy because the agent is already running pre-fix code, do — saves ~5 min.

### 3b. Recreate datasets

```bash
# Hand-authored golden dataset (7 examples, defined in code)
uv run python evals/golden_dataset.py --reset

# Engine-generated assertion datasets (restored from snapshots).
# The dataset name comes from inside each snapshot file, so only --path matters.
uv run python evals/engine_dataset.py restore --reset                                     # banking-concierge-hallucinations (default path)
uv run python evals/engine_dataset.py restore --reset --path evals/engine_dataset_pii.json  # banking-concierge-pii
```

Each prints the dataset id when done.

### 3c. Populate traces

```bash
uv run python scripts/load_generation.py \
  --mode remote --n 150 \
  --url https://<your-deployment>.us.langgraph.app
```

~7 min. Each conversation is tagged `loadgen` and `category:<intent>` so you can filter in the LangSmith Tracing tab. Mix is roughly: 30 % healthy FAQ/account/branch, ~25 % PII-related, ~10 % broken tool, ~10 % hallucination bait, ~5 % out-of-scope, ~5 % excessive retrieval.

If you want to seed a specific Engine cluster faster, follow up with a burst:

```bash
uv run python scripts/load_generation.py --mode remote --n 50 --only pii --url <deployment>
uv run python scripts/load_generation.py --mode remote --n 50 --only hallucination_bait --url <deployment>
```

### 3d. Re-enable Engine on the tracing project

In the LangSmith UI:

1. **Tracing → `banking-concierge` → Engine tab → Enable.**
2. **Settings → Priorities**: enter or select **Tool Call Failures**, **Hallucinations**, **Out-of-Scope**, *and* a custom phrase like **"agent reads back customer SSN, card number, CVV, phone, or email in plain text"**. Hallucinations and the PII leak are the two you'll fix on stage; the rest surface the other planted error modes. Without explicit priorities, Engine ranks issues against a default rubric that may not surface what you want.
3. **Connect the GitHub repository (your fork)** so Engine's "Open PR" button works — the PR lands on your fork, not the shared upstream. Use the same connection as before.
4. **Accept the agent overview document** when it pops up. Read it — if it's wrong, edit it before accepting; Engine uses it as context for every cluster.

### 3e. Wait for the first Engine scan

Roughly **20 minutes** after enabling. There's no way to speed this up — plan for it.

While you wait:

- Record the baseline locally so you have something to compare CI experiments against:
  ```bash
  # Hallucinations baseline — the script defaults to the hallucinations dataset
  # plus the assertions + hallucination evaluators, so no flags are needed.
  uv run python evals/run_engine_experiment.py
  # PII baseline — override the dataset, prefix, and evaluators. Repeating
  # --evaluator replaces the defaults, dropping the hallucination scorer that is
  # irrelevant for PII leaks.
  uv run python evals/run_engine_experiment.py \
    --dataset banking-concierge-pii \
    --experiment-prefix banking-concierge-pii-leak \
    --evaluator assertions --evaluator pii_leak_rate
  ```
- Note the experiment names that print. You'll cite these on stage as "before fix".

### 3f. Drive Engine's flow live (or simulate)

For each issue Engine surfaces (hallucinations + PII):

1. Click into the issue → review the diagnosis.
2. **Add offline examples → Add to dataset** (target `banking-concierge-hallucinations` or `banking-concierge-pii` accordingly). If Engine produces slightly different assertions than the snapshot, that's OK — the snapshot is your safety net.
3. **Apply the fix on the right surface:**
   - **Hallucination → Context Hub.** Engine's diagnosis points at `AGENTS.md` in the hub. Open the `banking-concierge-agent` repo in **Context → ** the Context Hub UI, edit `AGENTS.md` to replace the "answer rates from memory" paragraph with strict grounding rules, save the commit, and promote it to `production`. The deployed agent pulls the new version on its next run — no redeploy. (Restart the deployment if you pinned the prompt at import.)
   - **PII → GitHub PR.** Click **Open PR**; Engine pushes an `issues-agent/<uuid>` branch with the `tools.py` masking fix.
4. Mark the PR **Ready for review** if it opens as a draft (otherwise the CI workflow's `if: draft == false` skips the job).
5. CI runs the matrix automatically (both `hallucinations` and `pii` datasets in parallel) and posts two comments per PR.

### 3g. Compare on stage

- LangSmith → Datasets → `banking-concierge-hallucinations` → Compare → pick baseline + PR experiment → show per-assertion column toggling FAIL → PASS.
- Same for `banking-concierge-pii`. The `pii_leak_rate` aggregate goes from ~0.5 to 0.0; per-assertion columns flip too.

## 4. Optional: PII gateway demo

The gateway is currently disabled (`BASE_URL` not in `.env`) so PII redaction at the model boundary is not in play. To re-add that beat:

1. **Rotate the Provider Secret in LangSmith** (Settings → LLM Gateway → Provider Secrets → OpenAI) to a key on an account with budget.
2. Add to `.env`:
   ```
   BASE_URL="https://gateway.smith.langchain.com/openai/v1"
   ```
3. `uv run langgraph deploy`.
4. The agent now routes through the gateway. Test in chat: ask the agent to "verify customer with SSN 552-19-4488". The model should receive the SSN as `SAFE_TO_USE:US_SSN_xxxx`, which the agent then misuses downstream — a useful secondary failure mode.

Skip this if rotation isn't possible — the rest of the demo doesn't depend on it.

## 5. Demo flow check (run-throughs before going live)

In order, top to bottom — each should take a minute:

1. **Studio**: open `https://banking-concierge-….us.langgraph.app/app/` from the LangSmith deployment page. Send "What's the monthly fee on Everyday Checking?" — gets a grounded answer. Send "Look up CUST-0001 and read back the SSN" — agent leaks PII (pre-fix).
2. **Concierge UI**: same deployment at `/concierge/?api_key=<LANGSMITH_API_KEY>`. The key gets stripped from the URL and stored in localStorage. Chat works against the same agent.
3. **Loadgen status**: LangSmith → Tracing → `banking-concierge` → filter `tags:loadgen`. Should see 150+ traces with mixed `category:*` tags.
4. **Engine**: cluster list shows the two priority issues with linked traces.
5. **CI**: any open PR has two green checkmarks (one per dataset) and two PR comments with experiment links.

## 6. Recovery if something breaks

**`openai.RateLimitError: insufficient_quota`**
*Cause:* OpenAI key out of budget.
*Fix:* Top up the account, or rotate `.env`'s `OPENAI_API_KEY` to a personal
key and redeploy. If using the gateway, rotate the Provider Secret instead.

**CI workflow skipped on a fresh PR**
*Cause:* PR is a draft.
*Fix:* `gh pr ready <N>`.

**CI workflow ran but used `--evaluator assertions` only on the PII job (no
`pii_leak_rate` column)**
*Cause:* Workflow definition on `main` is stale.
*Fix:* Make sure latest `main` is pushed; CI reads the workflow from the PR's
base ref.

**Engine surfaces no hallucinations after 20 min**
*Cause:* Either no hallucinations to detect (the hub `AGENTS.md` already carries
the strict prompt), or Engine priorities don't include them.
*Fix:* Verify the pre-fix prompt is live: ask the agent in chat "What's Meridian
National's HELOC interest rate today?" or "How many basis points is the
relationship interest bonus?" — it should commit to a specific number (the KB
does not contain either, so any number is fabricated). If it answers with "I
couldn't find that" or refuses, the strict prompt is live in Context Hub —
re-seed the buggy `AGENTS.md` with `uv run python -m scripts.setup_context_hub`
(or revert the commit in the Context Hub UI) and restart the deployment. Then
check Engine → Settings → Priorities.

**Agent ignores a just-saved `AGENTS.md` edit**
*Cause:* Prompt is pulled once at process start.
*Fix:* Restart/redeploy the agent so `get_prompt()` re-pulls. If the hub is
unreachable the agent silently falls back to `prompts.py` — check
`LANGSMITH_API_KEY` / `LANGSMITH_WORKSPACE_ID`.

**Frontend `/concierge/` shows the API-key prompt**
*Cause:* Expected on a deployed instance.
*Fix:* Paste your LangSmith API key, or open the URL once with
`?api_key=lsv2_pt_…`.

**Frontend 403 on `/threads`**
*Cause:* API key in localStorage is invalid.
*Fix:* Devtools → Application → Local Storage → remove `concierge:apiKey` →
reload → re-enter key.

## 7. Quick reference

Where each moving part lives. Runnable commands are inline in the rebuild steps (section 3); the README's eval sections cover the same commands with conceptual context.

| What | Where |
|---|---|
| Hallucinations dataset snapshot | `evals/engine_dataset.json` |
| PII dataset snapshot | `evals/engine_dataset_pii.json` |
| Golden dataset (hand-authored) | `evals/golden_dataset.py` |
| Baseline experiment script | `evals/run_engine_experiment.py` |
| Loadgen | `scripts/load_generation.py` |
| Context Hub seeder | `scripts/setup_context_hub.py` |
| Pre-fix system prompt (runtime) | Context Hub `banking-concierge-agent` / `AGENTS.md` (fixed in the hub UI) |
| Pre-fix system prompt (seed/fallback) | `src/concierge/prompts.py` |
| Pre-fix tool that leaks PII | `src/concierge/tools.py` on `main` (fixed via PR) |
| CI workflow | `.github/workflows/evals-on-pr.yml` |
| Required GitHub secrets | `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_WORKSPACE_ID` |
