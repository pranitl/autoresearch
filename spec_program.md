# spec_program

You are running an autonomous copy-optimization loop on a single tracked file: `page_spec.md`.

## Goal

Maximize click-through rate on these primary actions:

- `Request Pricing`
- phone clicks for `(781) 874-9901`
- service `Learn More` links
- `Contact Our Team`

You are optimizing for clicks, not downstream form submissions.

## Scope

- You may edit only `page_spec.md`.
- You may not edit this program file, `scoring_rubric.md`, the repo docs, the runner, or any logs.
- The runner will score every candidate and automatically keep winners or revert losers.

## Editing rules

- Make exactly one small, targeted improvement per round.
- For this run, change exactly one of these sections per round:
  - `Owners Section`
  - `Featured Page`
  - `SEO Content`
  - `FAQs`
- Keep all non-editable content unchanged.
- Preserve every hard constraint already present in `page_spec.md`.
- Treat every `### Locked Notes` block in `page_spec.md` as non-editable page structure.
- Do not edit `Hero` or `Services Grid` in this run.

## Optimization heuristics

- Prefer changes that create an immediate reason to click now.
- Increase specificity before adding volume.
- Favor copy that reduces family anxiety, clarifies next steps, and makes pricing/contact clicks feel low-friction.
- Use trust elements only when they strengthen action intent.
- Avoid hype, broad generic claims, or copy that sounds ad-like.
- Avoid repeating ideas that already failed unless you are improving them from a different angle.
- When testing local relevance, use only the confirmed service areas listed in `page_spec.md`.
- Test local town combinations selectively; do not stuff the full service-area list into every section.

## Section guidance

- `Hero`: leave unchanged for this run.
- `Owners Section`: strengthen empathy, affordability, proof, and risk reduction. You may test different town combinations in the section headline and supporting copy when they improve local relevance without feeling stuffed.
- `Services Grid`: leave unchanged for this run.
- `Featured Page`: optimize the current `About us` selection by changing the custom headline and custom content only. Keep the selected page as `About us`, keep the content plain text only, and stay within the 200-character limit.
- `SEO Content`: improve skimmability, local trust, and action intent while staying paste-clean for WordPress blocks. You may test different service-area mentions where they appear naturally.
- `FAQs`: both the questions and the answers are editable. Keep 5 FAQ items total and make them clearer, more reassuring, more action-oriented, and locally relevant where a town reference adds credibility.

## Output discipline

- Return only the single updated section.
- Include that section's marker line, for example `1. Hero`.
- Do not return the full file.
- Do not return a patch.
- Make the single intended improvement obvious and defensible.
