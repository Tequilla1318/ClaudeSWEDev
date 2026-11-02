# Design: Local LLM fallback ("migration package")

Status: **draft, awaiting owner approval**. No implementation until this PR is approved.

## 1. Goal
If Claude (or any hosted AI service) becomes unavailable, unaffordable, or undesirable, the owner can
switch this repo's AI workflow to **open-weight models running on a home server**, with minimal change
to how work is requested, reviewed, and merged on GitHub.

Success = the owner flips one switch, labels an issue, and a locally hosted agent produces a branch and a
pull request with tests and a code-review write-up, following the same `CLAUDE.md` rules.

## 2. Non-goals
- Matching frontier-model quality. Local models in the 32 GB class are behind the frontier, so the
  fallback is expected to handle smaller, well-specified stories, not open-ended design work.
- Training models from scratch. Fine-tuning is out of scope for v1 (see §6.6).
- Running anything on the owner's personal computer. The home server is a separate, dedicated machine.

## 3. Key insight: what is portable and what is Claude-specific
| Part of today's workflow | Portable? | Plan |
|---|---|---|
| `CLAUDE.md` working agreement | Mostly | Move the rules to `AGENTS.md` (an open convention many agents read); `CLAUDE.md` imports it |
| PR/issue templates, CI, branch rules | Yes | Unchanged |
| `context.md` / `decisions.md` per project | Yes | Unchanged; the local agent reads them too |
| Cloud VM sessions (Claude Code on the web) | No | Replaced by a container on the home server |
| Wake-on-merge (scheduled task API trigger) | No | Same workflow, second backend: a self-hosted runner job |
| GitHub access through Anthropic's proxy | No | A fine-grained token for the AI account, held only by the runner |

Most of the "package" is therefore **plumbing**, not prompts: the conventions already live in the repo.

## 4. "A team of 32 GB models" — what actually helps
- **Combined memory beats separate small models.** Four 32 GB machines can each run a ~30B model, but
  one machine with 128 GB can run a single ~100B+ mixture-of-experts model, which is markedly stronger.
  Splitting one model across machines over a network is possible (e.g. llama.cpp RPC) but slow.
- **Role splitting helps modestly.** A planner, a coder, and a reviewer (possibly the same model with
  different prompts) catch more mistakes than a single pass, especially with tests as the referee.
- **Tests are the real verifier.** The agent loops until CI-equivalent checks pass locally, and the PR
  states honestly when they don't.
- **Fresh knowledge comes from retrieval, not retraining.** The agent searches the repo, its docs, and
  vendored reference material instead of relying on what the model memorized.

## 5. Architecture
```
GitHub (Tequilla1318/ClaudeSWEDev)
  │  issue labeled `agent:local`, PR merged, or `/local` comment
  ▼
Self-hosted GitHub Actions runner (home server, ephemeral, private-repo only)
  │  starts a throwaway container per job
  ▼
Agent container (Docker): repo checkout + open-source coding agent + test toolchain
  │  OpenAI-compatible HTTP API (localhost only)
  ▼
Model server (llama.cpp server / Ollama / vLLM) ── optional router (e.g. LiteLLM) for planner/coder/reviewer
  │
  ▼
Branch pushed + PR opened via GitHub REST API, using .github/pull_request_template.md
```

### 5.1 Backend switch
A repository variable `AGENT_BACKEND` = `claude` (default) | `local` | `both`.
`wake-claude.yml` (PR #6) is generalized to `wake-agent.yml` and routes to the scheduled-task API
(`claude`) or dispatches a job to the self-hosted runner (`local`).

### 5.2 Agent choice
Use an existing open-source coding agent that supports OpenAI-compatible local endpoints and a headless
mode, rather than writing one. Candidates are evaluated in story S5 with the eval harness; the design does
not hard-code one, because this field changes monthly.

### 5.3 Model choice
Chosen by the eval harness (S5) at migration time, from whatever open-weight models are best then.
Hardware tiers, assuming 4-bit quantization:

| Memory available to the model | Realistic model class | Expected use |
|---|---|---|
| 32 GB | ~24–35B dense, or ~30B MoE | Small, well-specified stories; reviews |
| 64 GB | ~70B dense, or ~100B MoE at lower precision | Most single-module stories |
| 128 GB+ | ~100–120B MoE | Multi-file stories; planner role |

On a PC, "memory" means GPU VRAM for speed; system RAM works but is several times slower.
Apple Silicon unified memory counts fully.

## 6. Safety and security
1. **Isolation.** Each job runs in a fresh container with only the checkout mounted, no host home
   directory, and network limited to GitHub, package registries, and the local model server.
2. **Self-hosted runners on public repos are dangerous**: a fork's PR could run code on the server.
   The local runner must only accept jobs from the owner's events (`github.actor` check), never from
   fork PRs, and **the repo should be private** before the runner is registered.
3. **Token.** A fine-grained token for the AI GitHub account, scoped to this repo, stored as an Actions
   secret, with an expiry date. The agent never sees the owner's main account.
4. **Branch protection** unchanged: the agent opens PRs, the owner merges.
5. **Model server** listens on localhost / the container network only, not the LAN or internet.
6. **Fine-tuning (later).** If ever needed, LoRA fine-tunes on this repo's merged PRs; out of scope for v1.

## 7. Milestones → stories
| # | Story | Testable in the cloud? |
|---|---|---|
| S1 | Portable conventions: move rules to `AGENTS.md`, `CLAUDE.md` imports it; no behavior change for Claude | Yes |
| S2 | Backend switch: generalize wake workflow, `AGENT_BACKEND` variable, `agent:local` label trigger | Yes (dry run) |
| S3 | Agent container: Dockerfile, entrypoint that reads issue → branch → runs agent → runs tests → opens PR via REST | Partly (with a mock model endpoint) |
| S4 | Home server kit: `docker compose` for model server + router + runner, setup script, hardware guide | No — documented, owner runs on server |
| S5 | Eval harness: replay a fixed set of past stories with tests; report pass rate per model/agent combo | Partly (tiny model on CPU) |
| S6 | Fire drill: monthly workflow that runs one small story on the local backend and reports health | No — needs the server |
| S7 | Retrieval: index repo docs + vendored references for the agent | Yes |

Order: S1 → S2 → S3 → S5 → S4 → S6 → S7. S1–S3 are useful even before any hardware is bought.

## 8. Testing and validation
- S1–S3: unit tests for the entrypoint (issue parsing, branch naming, PR body rendering) against a
  mock OpenAI-compatible server; workflow syntax checked with `actionlint`.
- S5: the harness itself is the validation — a model/agent pair "passes" a story only if the story's
  original tests pass on its output.
- Limitation: cloud sessions can't download most model weights (the model host isn't on the default
  network allowlist) and have no GPU, so real-model testing happens on the home server.

## 9. Risks
- **Quality gap.** Local output will need more review; PRs from the local backend are labeled
  `agent:local` so the owner knows.
- **Speed.** CPU-only inference can take tens of minutes per story.
- **Moving target.** Agents and models change fast; the eval harness, not this doc, picks them.
- **Hardware cost** is the owner's call (see open questions).

## 10. Open questions for the owner
1. **Hardware:** existing machine, or buying one? GPU (which, how much VRAM) or Apple Silicon
   (how much unified memory)? Budget?
2. **Mode:** cold standby (only used if Claude is unavailable) or hybrid (local handles small stories
   now, Claude the hard ones)?
3. **Repo visibility:** OK to make ClaudeSWEDev private? Strongly recommended before registering a runner.
4. **Scope of the fallback:** code only, or also design docs and reviews?
