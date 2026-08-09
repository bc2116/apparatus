# Contributing

## Setup

The repository is a [uv](https://docs.astral.sh/uv/) workspace.

```bash
uv sync --all-packages
uv run pytest
```

Python ≥ 3.10; uv manages the interpreter (see `.python-version`).

## How work is organized

- Development follows the phased plan in [docs/plan/README.md](docs/plan/README.md).
  Each planned change is a focused pull request with a self-contained prompt file
  that any contributor — human or AI agent — can execute in a cold session.
- One PR per branch, named `pr-XX-short-slug`. Do not bundle planned PRs.
- Every PR keeps `conformance/` green. Fixtures change only deliberately, in the
  same PR that intentionally changes the behavior they pin — never loosened to
  make a failure pass.
- Update the status table in `docs/plan/README.md` when a PR lands.

## Definition of done

1. The deliverables in the PR's prompt file exist at the specified paths.
2. Acceptance criteria are verified, and the PR description says how.
3. `uv run pytest` is green.
4. The diff is focused — nothing outside the PR's scope.

## Sign-off (DCO)

All commits must carry a Developer Certificate of Origin sign-off
(`git commit -s`), certifying <https://developercertificate.org/> (v1.1):

```
Signed-off-by: Your Name <your@email>
```

## Style

- Vocabulary in all product- and user-facing text follows
  [docs/adr/ADR-0001-vocabulary.md](docs/adr/ADR-0001-vocabulary.md).
- Core code and starter content obey the harness-agnostic contract in
  [docs/adr/ADR-0003-harness-agnostic-contract.md](docs/adr/ADR-0003-harness-agnostic-contract.md).
- Plain, direct prose. No marketing language in docs.

## AI agents

[AGENTS.md](AGENTS.md) is the canonical instruction file for agent contributors.
