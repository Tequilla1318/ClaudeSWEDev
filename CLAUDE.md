# Working agreement for Claude

This repo is a workspace for many independent software projects. The owner describes an idea
(often from a video, paper, or article); Claude designs, builds, tests, and opens PRs for review.

## Hard rules
- **Everything runs in the cloud session.** Never ask the owner to run code locally and never use
  tools that reach the owner's computer.
- **Never commit to `main` directly.** Every change goes through a branch and a pull request.
  The owner reviews and merges.
- **Never commit secrets** (API keys, tokens, passwords). Use environment-level network secrets.

## Repo layout
- Each project lives in `projects/<project-name>/` (kebab-case) and is self-contained:
  its own `README.md`, dependency file (e.g. `pyproject.toml`), `src/`, and `tests/`.
- Shared tooling (CI, templates) lives in `.github/`.

## Project context (memory between sessions)
Sessions start from a fresh clone and remember nothing else, so each project keeps its own context:
- `projects/<name>/docs/context.md` — current state: what's built, what's in progress, what's next,
  known issues and gotchas. Keep it short and current; rewrite stale parts rather than appending.
- `projects/<name>/docs/decisions.md` — append-only log of design decisions:
  date, decision, why, alternatives rejected.

**At the start of a session** on a project, read both files before doing anything else.
Then read the owner's feedback on GitHub (see "Reading owner feedback" below).
**In every PR**, update `context.md` (and `decisions.md` if a decision was made) as part of the change.

## Reading owner feedback
The owner leaves feedback as comments on PRs and issues, often after closing or merging them.
Closed and merged items stay readable, so at the start of every session on a project:
1. List the project's PRs and issues updated since the date at the top of `context.md`'s
   "Feedback last read" line, **including closed and merged ones**:
   `gh api "repos/Tequilla1318/ClaudeSWEDev/issues?state=all&since=<ISO date>&per_page=100"`
   (this returns issues *and* PRs; filter by project name in the title or body).
2. For each, read all three comment kinds:
   - conversation: `gh api repos/Tequilla1318/ClaudeSWEDev/issues/<n>/comments`
   - review summaries: `gh api repos/Tequilla1318/ClaudeSWEDev/pulls/<n>/reviews`
   - inline code comments: `gh api repos/Tequilla1318/ClaudeSWEDev/pulls/<n>/comments`
3. Act on it: open follow-up issues/stories for requested changes, record decisions in `decisions.md`,
   and update the "Feedback last read: <date>" line in `context.md` in the next PR.
4. If a comment is unclear, ask in the session rather than guessing.

Notes: GraphQL is blocked from cloud sessions, so `gh pr create`/`gh pr view` fail; use the REST API via
`gh api` (if `GH_TOKEN` is set but invalid, prefix with `env -u GH_TOKEN`). Claude only reads comments
while a session is running; it is not notified when an issue closes.

## Agile workflow
1. **Backlog = GitHub issues.** Each feature is a user story using the "User story" issue template,
   with acceptance criteria. Larger efforts are an epic issue that links its stories.
2. **Starting a new project:** first open a PR containing only a design doc at
   `projects/<name>/docs/design.md` (goal, scope, approach, math/physics references, architecture,
   milestones broken into stories, open questions). Implementation starts after the owner approves it.
3. **One story = one branch = one PR.** Branch names: `feat/<project>-<short-desc>`,
   `fix/<project>-<short-desc>`, `docs/...`, `chore/...`.
4. **Small PRs.** Aim for under ~400 changed lines; split otherwise.
5. **Commits** follow Conventional Commits: `feat(hpop): add J2 perturbation`.
6. Keep each project's `README.md` and `docs/` current as part of the same PR.

## Definition of Done (every PR)
- Acceptance criteria of the linked issue are met; PR says `Closes #<n>`.
- Unit tests added/updated; all tests pass in CI.
- Lint passes (Python: `ruff check`). Formatting: `ruff format` by default; a project that declares
  `[tool.black]` in its `pyproject.toml` is formatted with **black** instead, and CI checks it with
  `black --check`. Don't mix the two formatters in one project.
- Public functions have docstrings and type hints.
- Numerical / scientific code is validated against a reference (published values, analytic case,
  or established library) and the validation is described in the PR.
- PR description is filled in fully using the template — it is the code review document.

## Code review write-up (PR description)
Write it for a reviewer who has not seen the session: what and why, a walkthrough of key changes,
how it was tested/validated, risks and limitations, and anything the owner should decide.
Be honest about shortcuts, known bugs, and untested paths.

## Defaults
- Language: Python 3.11+ unless the project needs otherwise (state the reason in the design doc).
- Tests: `pytest`. Numerics: `numpy`/`scipy`. Prefer well-maintained libraries over hand-rolling,
  unless the point of the project is to implement it from scratch (say which in the design doc).
