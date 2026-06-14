# Talk track: how LangSmith accelerates the agent development lifecycle

Bullet-point speaker notes. Use the Meridian National Customer Service Concierge in this repo as the running example throughout.

## Open

- Agents fail differently than web apps. The failures are stochastic, content-dependent, and only show up in production at scale. Traditional observability tells you a request was slow; it doesn't tell you the agent fabricated a HELOC rate to a CSR who's on a live call with a customer.
- LangSmith covers the full agent lifecycle in one product: trace it, understand how it's used, detect failures, diagnose them in your own source code, propose the fix, prove the fix worked offline, and prevent the issue from returning. Each step compresses what used to be a multi-team, multi-week investigation into a workflow that a single engineer can drive in an afternoon.

## 1. Build and ship — get traces flowing on day 1

- Deploy from your repo with one command (`langgraph deploy`). Custom routes mount a frontend alongside the agent server, so your full chat UI is at the same origin as the agent's `/threads` and `/runs` APIs.
- The moment a real conversation lands, the full trace — every model call, every tool invocation, every retrieved chunk — is in LangSmith. Zero instrumentation beyond setting an env var.
- This demo: the concierge runs on a LangSmith deployment, a React UI is mounted at `/concierge/`, traces flow into the tracing project automatically.
- The agent's instructions don't live in the code — they live in the **Context Hub** as a versioned `AGENTS.md`, pulled at runtime. The repo keeps a one-file breadcrumb (`src/concierge/context.py`) that says "the prompt is in the hub." Context Hub also versions a library of `SKILL.md` capabilities alongside the agent. This matters in step 5: a class of fix lands in the hub, not in a code PR.

## 2. Understand actual usage — Insights

- **The question Insights answers:** what are users *actually doing* with the agent, vs. what you designed it for?
- Cluster runs into intent buckets without writing a single line of analysis code. Use auto-clustering, or define your own categories — for the concierge: product/policy questions, account lookups, identity verification, money movement, branch & ATM locator.
- Each run gets summarized by an LLM using a prompt you control, so the summaries align with the categories you care about. Aggregate across thousands of conversations to see workflow distribution, top topics per category, and drift over time.
- Practical wins:
  - PMs learn which features see real usage and which don't — kills speculation-driven roadmap arguments.
  - Surfacing of out-of-scope requests as a "potential next feature" signal.
  - Drift detection: if "identity verification" goes from 5% to 30% of volume in a week, that's a leading indicator something changed in CSR workflows.

## 3. Detect failures — Engine clusters them automatically

- **The question Engine answers:** out of the 50,000 traces my agent ran last week, which ones are the same recurring problem?
- Engine scans your traces continuously, clusters failures into named issues, and surfaces only the recurring ones — not noise. Tool-call failures, hallucinations, latency anomalies, out-of-scope behavior, PII leaks.
- You set priorities once ("agent fabricates banking facts", "agent reads back full SSN"), and Engine ranks issues against those priorities so the most important clusters surface first.
- This demo: after one loadgen run, Engine surfaced two distinct issues — one about hallucinated CD / HELOC / mortgage rates, one about plaintext PII read-back — without anyone reading individual traces.

## 4. Diagnose root cause — in your own source code

- Engine doesn't just point at failures; it reads your connected repo **and your Context Hub** and **cites where the behavior comes from** — a file and line in code, or the `AGENTS.md` in the hub.
- Example from this demo: the hallucinations issue's diagnosis traced the behavior to the agent's `AGENTS.md` in Context Hub — quoting the problematic phrasing ("'fill in the gap from your training-time knowledge', and bans hedging phrases like 'I couldn't find that'") — and cross-referenced the banking docs to point out the internal contradiction ("the banking docs explicitly say 'direct readers to live disclosures'"). The PII issue, by contrast, was traced to `src/concierge/tools.py`.
- For a banking audience: Engine framed business impact in regulatory terms — "creating regulatory and reputational exposure" — not just "model hallucination". That kind of diagnosis is normally hours of human work per cluster.

## 5. Propose the fix — Engine recommends a fix on the right surface

- Engine routes the fix to wherever the behavior actually lives — and this demo deliberately has **two surfaces**:
  - **Hallucination → Context Hub.** The fix is an edit to `AGENTS.md` in the Context Hub UI: replace the "answer rates from memory" paragraph with strict grounding rules, commit, promote to `production`. The deployed agent pulls the new version on its next run — **no code change, no redeploy**. Instruction changes ship at the speed of a prompt edit, with full version history and one-click rollback.
  - **PII → GitHub PR.** One click → Engine opens an `issues-agent/<uuid>` PR in your connected repo that masks PII fields at the tool boundary — a surgical, reviewable code diff.
- The point: prompt/policy fixes don't have to go through the code-deploy pipeline, and code fixes still get the rigor of a reviewed PR. Same Engine loop, right tool for each bug.

## 6. Prove the fix worked — eval datasets from real failures

- Engine takes the *real production traces* that triggered the issue and promotes them into a dataset — the actual failing conversations, not synthetic test cases.
- This kills the eternal problem of "what should we test for?" — your offline test cases now come directly from the failure modes you've seen in prod.
- Plug the dataset into an experiment runner and an LLM-as-judge evaluator (here, a hallucination-grounding judge plus a deterministic PII-leak check) and you have an offline regression test for that exact issue, generated in seconds.

## 7. Close the loop on every PR — CI integration

- This demo wires a GitHub Action that, on every PR, runs the Engine-generated dataset against the PR's code and posts the experiment link back as a PR comment.
- Reviewers see the before/after score diff in LangSmith → "the hallucination rate dropped to zero" — no redeploy needed.
- Matrix over all Engine-discovered datasets means cross-impact regressions are caught for free: a PII fix that accidentally degraded hallucination grounding would show up immediately in the hallucination dataset's PR comment.

## 8. Prevent regressions — Engine deploys the evaluator

- Engine generates a custom online evaluator from the same diagnosis and one-click deploys it to the project.
- If the issue returns post-merge, the evaluator fires on the offending trace, Engine **automatically reopens the closed issue**, and you know within the next scan instead of next quarter when a customer complains.
- The loop is closed without any tooling outside LangSmith.

## What's new that makes this possible

- **Engine**: turns reactive trace review into a closed-loop continuous-improvement system. Detect → diagnose → propose fix → generate eval → prevent regression. All in one product.
- **Context Hub**: version-controlled, environment-aware storage for the agent's instructions (`AGENTS.md`) and skills (`SKILL.md`), pulled at runtime. Lets Engine fix prompt/policy bugs as a promoted hub commit — no code redeploy — while code bugs still flow through a reviewed PR.
- **Insights**: turns trace volume into product intelligence. What people do, in what shape, at what frequency, with what categories you care about.
- **LangSmith deployment**: the agent and the eval infrastructure run on the same platform that observes them. No round-trip between "where the agent runs" and "where you analyze it".

## Closing

- The customer wins because the agent gets better, faster, with fewer failure modes leaking to end users.
- The engineering team wins because failures stop being individual fire drills and start being a steady pipeline of PRs against named, ranked issues.
- The business wins because regulatory and reputational risk surfaces at the **issue cluster** level — well before it hits a board-level incident.
- LangSmith is how AI applications get reliable at production scale, with the team you already have.
