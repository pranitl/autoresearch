# CRO Judge Loop

LLM-as-judge optimization loops for conversion-focused marketing assets.

This repo keeps the useful part of the original autonomous research pattern: an
agent proposes one controlled challenger, a locked judge rubric scores it against
the current champion, and the runner keeps only strict improvements. Instead of
optimizing model weights, the loop optimizes landing-page sections, CTAs, and
Google Ads RSA copy using Codex CLI by default, with OpenRouter available as a fallback backend.

## What This Does

- Drafts one targeted challenger per round.
- Applies the challenger to a single editable section of the working spec.
- Validates structural constraints before spending judge calls.
- Scores the candidate with a locked LLM judge rubric.
- Keeps winners, rejects losers, and records every round under `.runs/<tag>/`.
- Preserves an A/B-testing style champion history for later review.

The loop is deliberately document-first. The `.md` spec files describe the
current asset, locked constraints, and editable surface. The Python runners
enforce structure, call the models, and save artifacts.

## Workflows

### Landing Pages and CTAs

Use `spec_loop.py` for landing-page, CTA, and page-section experiments.

Key files:

- `page_spec.md` - current landing-page champion and editable sections
- `spec_program.md` - standing instructions for the mutator model
- `scoring_rubric.md` - locked judge rubric
- `spec_loop.py` - runner, validator, model calls, artifact handling

Run:

```bash
uv run spec_loop.py --spec page_spec.md --tag <tag>
```

Useful options:

```bash
uv run spec_loop.py --spec page_spec.md --tag <tag> --rounds 25
uv run spec_loop.py --spec page_spec.md --tag <tag> --no-git
uv run spec_loop.py --spec page_spec.md --tag <tag> --allowed-sections Hero "Services Grid"
```

### RSA Ad-Copy Hypotheses

Use `rsa_spec_loop.py` for Google Ads responsive search ad challenger specs.

Key files:

- `rsa_audit_spec.md` - current RSA audit/champion spec
- `rsa_spec_program.md` - standing instructions for RSA mutation
- `rsa_scoring_rubric.md` - locked RSA judge rubric
- `rsa_spec_loop.py` - RSA-specific runner and validator
- `search_core.py` - shared search-controller utilities

Run:

```bash
uv run rsa_spec_loop.py --spec rsa_audit_spec.md --tag <tag>
```

The RSA loop can also retain novel non-winning candidates for broader search:

```bash
uv run rsa_spec_loop.py --spec rsa_audit_spec.md --tag <tag> --search-policy socratic-search
```

## Setup

Requirements:

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- OpenRouter API access

Install dependencies:

```bash
uv sync
```

Configure models:

```bash
cp .env.example .env
```

Default Codex CLI backend:

```bash
MODEL_BACKEND=codex_cli
CODEX_MUTATOR_MODEL=gpt-5.5
CODEX_PANEL_MODEL=gpt-5.5
CODEX_JUDGE_MODEL=gpt-5.5
CODEX_MUTATOR_REASONING_EFFORT=low
CODEX_PANEL_REASONING_EFFORT=low
CODEX_JUDGE_REASONING_EFFORT=high
```

OpenRouter fallback:

```bash
MODEL_BACKEND=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MUTATOR_MODEL=x-ai/grok-4.3
OPENROUTER_PANEL_MODEL=google/gemini-3.1-pro-preview
OPENROUTER_JUDGE_MODEL=google/gemini-3.1-pro-preview
OPENROUTER_MUTATOR_REASONING_EFFORT=medium
OPENROUTER_PANEL_REASONING_EFFORT=high
OPENROUTER_JUDGE_REASONING_EFFORT=high
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=https://your-site.example
OPENROUTER_APP_NAME=cro-judge-loop
```

## Artifacts

Each run writes to `.runs/<tag>/`:

- `rounds.jsonl` - machine-readable round history
- `winner.md` - latest winning spec
- `final_report.md` - summary report
- `raw/` - raw mutator responses
- `candidates/` - candidate specs
- `judgements/` - raw judge responses

When git integration is enabled, the runner creates a branch using the workflow
prefix and commits winning spec versions.

## Project Structure

```text
spec_loop.py                 landing-page/CTA optimization loop
rsa_spec_loop.py             RSA ad-copy optimization loop
search_core.py               shared search-controller utilities
page_spec.md                 landing-page champion spec
spec_program.md              landing-page mutator instructions
scoring_rubric.md            landing-page judge rubric
rsa_audit_spec.md            RSA champion/audit spec
rsa_spec_program.md          RSA mutator instructions
rsa_scoring_rubric.md        RSA judge rubric
tests/                       validator and prompt tests
```

## Testing

```bash
uv run python -m unittest discover -s tests
```

## License

MIT
