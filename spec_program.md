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
- For this run, change exactly one section per round:
  - `Hero`
  - `Owners Section`
  - `Services Grid`
  - `Videos`
- Keep all non-editable content unchanged.
- Preserve every hard constraint already present in `page_spec.md`.
- Treat every `### Locked Notes` block in `page_spec.md` as non-editable page structure.
- Do not edit `Featured Page`, `SEO Content`, or `FAQs` in this run.

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

- `Hero`: optimize only the `Hero Keyword` field. Corporate automatically appends `in Boston Northwest` to the rendered line, so write the editable text to read naturally before that suffix. Avoid repeating `Boston Northwest` in the editable field, and keep the full rendered headline concise enough to fit the current layout cleanly.
- `Owners Section`: optimize only the main `Headline` line above the owner copy. Do not change the section label, phone link, or owner body copy. Test clearer benefit framing, local relevance, and stronger click pull without stuffing town names.
- `Services Grid`: optimize only the `Services headline` and `Services intro` text. Do not change the displayed services or additional service options. Make the headline and intro more click-oriented for `Learn More` links by clarifying fit, reducing decision friction, and making the featured services feel immediately relevant. You may test one or two local town references when they sound natural, but do not stuff town names.
- `Featured Page`: leave unchanged for this run.
- `Videos`: optimize only the `Video headline` and `Video description`. Keep the focus on trust, caregiver quality, peace of mind, and local relevance that can increase later pricing/contact clicks. Do not change the video embeds/media.
- `SEO Content`: leave unchanged for this run.
- `FAQs`: leave unchanged for this run.

## Output discipline

- Return only the single updated section.
- Include that section's marker line, for example `1. Hero`.
- Do not return the full file.
- Do not return a patch.
- Make the single intended improvement obvious and defensible.
