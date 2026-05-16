"""
RSA audit optimization loop for Google Ads responsive search ad experiments.

This mirrors the existing `spec_loop.py` workflow, but swaps the page-spec domain
for a document-first RSA optimization spec grounded in the March 29 audit.

Usage:
    uv run rsa_spec_loop.py --spec rsa_audit_spec.md --tag 20260329-rsa-audit
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from search_core import (
    SEARCH_POLICIES,
    SOCRATIC_SEARCH_POLICY,
    CandidateRecord,
    SearchDecision,
    build_search_decision,
    candidate_record_to_dict,
    candidate_signature,
    load_search_archive,
    normalize_private_judge_signal,
    novelty_against_archive,
    save_search_archive,
    should_retain_candidate,
)
from spec_loop import (
    Mutation,
    Judgement,
    OpenRouterClient,
    SpecLoopError,
    append_jsonl,
    ensure_git_branch,
    ensure_git_repo,
    extract_json_object,
    format_score,
    get_reasoning_config,
    get_repo_root,
    git_commit_path,
    load_dotenv,
    load_jsonl,
    load_resume_state,
    load_text_file,
    parse_mutation,
    persist_round_artifacts,
    recent_history,
    replace_current_champion_score,
    require_env,
    write_text,
)


SECTION_ORDER = [
    "Locked Audit Context",
    "Core Non-Medical Home Care",
    "Private Home Care Near Me",
    "Locked Reference Ad Groups",
]

SECTION_MARKERS = {
    "Locked Audit Context": "1. Locked Audit Context",
    "Core Non-Medical Home Care": "2. Core Non-Medical Home Care",
    "Private Home Care Near Me": "3. Private Home Care Near Me",
    "Locked Reference Ad Groups": "4. Locked Reference Ad Groups",
}

ACTIVE_SECTIONS = [
    "Core Non-Medical Home Care",
    "Private Home Care Near Me",
]

FRONTIER_TRACKS = [
    "conservative",
    "differentiated",
    "synthesis",
]

TRACK_LABELS = {
    "conservative": "Conservative",
    "differentiated": "Differentiated",
    "synthesis": "Synthesis",
}

TRACK_STRATEGIES = {
    "conservative": (
        "Stay close to the strongest proven concepts and improve precision, clarity, "
        "and query fit without drifting into low-value rewrites."
    ),
    "differentiated": (
        "Try a meaningfully different but still evidence-grounded angle that could expand "
        "the final asset bank without weakening private-pay intent."
    ),
    "synthesis": (
        "Combine the strongest ideas discovered so far into the most promotion-worthy final "
        "candidate, not just the safest or most novel version."
    ),
}

SCORE_CATEGORY_MAXES = {
    "query_message_fit": 20.0,
    "ctr_lift_vs_live_comparators": 20.0,
    "click_quality_protection": 15.0,
    "trust_private_pay_specificity": 15.0,
    "landing_page_fit": 10.0,
    "rsa_diversity_strength": 10.0,
    "policy_brand_safety": 10.0,
}

SCORE_LINE_RE = re.compile(
    r"(?m)^Current champion score:\s*([0-9]+(?:\.[0-9]+)?)/100\s*$"
)

EDITABLE_MARKER = "### Editable Challenger"

ALLOWED_SECTION_URLS = {
    "Core Non-Medical Home Care": "https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/",
    "Private Home Care Near Me": "https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/",
}

FORBIDDEN_COPY_TERMS = {
    "assisted living",
    "career",
    "careers",
    "child care",
    "childcare",
    "hospice",
    "job",
    "jobs",
    "medicaid",
    "medicare",
    "nursing home",
    "training",
}

THEME_KEYWORDS = {
    "brand": ("firstlight",),
    "location": (
        "arlington",
        "boston",
        "cambridge",
        "lexington",
        "local",
        "medford",
        "melrose",
        "near me",
        "near you",
        "nw",
        "somerville",
        "woburn",
        "winchester",
    ),
    "service": (
        "adult home",
        "caregiver",
        "companion",
        "home care",
        "in-home",
        "in home",
        "private duty",
        "private pay",
        "private-pay",
        "senior care",
    ),
    "trust": (
        "background",
        "family-owned",
        "family owned",
        "licensed",
        "insured",
        "trained",
        "trusted",
    ),
    "usp": (
        "care advisor",
        "consult",
        "flexible",
        "minimum",
        "private pay",
        "private-pay",
        "service",
    ),
    "cta": (
        "call",
        "free",
        "get care",
        "start",
        "talk",
        "today",
        "this week",
    ),
    "empathy": (
        "adult child",
        "aging parents",
        "family",
        "help",
        "mom",
        "dad",
    ),
}


@dataclass
class ParsedSpec:
    header: str
    sections: dict[str, str]


@dataclass
class FrontierEntry:
    spec_text: str
    score: float
    source_round: int
    changed_section: str
    change_summary: str


@dataclass(frozen=True)
class PersonaJudge:
    persona_id: str
    name: str
    role: str
    background: str
    pain_points: list[str]
    buying_triggers: list[str]
    search_intent: str


@dataclass
class PersonaJudgement:
    persona: PersonaJudge
    judgement: Judgement


HOME_CARE_PERSONAS = [
    PersonaJudge(
        persona_id="overwhelmed_adult_child",
        name="The Overwhelmed Adult Child",
        role="Primary decision-maker",
        background=(
            "Adult child, typically late 40s to early 60s, balancing a full-time "
            "career, children, and an aging parent's declining health from a "
            "distance or on top of a packed schedule."
        ),
        pain_points=[
            "Severe guilt over not being able to provide the care themselves.",
            "Chronic stress and burnout from acting as part-time caregiver and full-time project manager.",
            "Anxiety over falls, wandering, medication misses, dementia, or Alzheimer's decline.",
            "Low trust caused by opaque care options and poor communication.",
        ],
        buying_triggers=[
            "A fall, wandering incident, missed critical medication, visible home hygiene decline, or poor nutrition.",
        ],
        search_intent=(
            "High-intent, solution-oriented, and urgency-driven. Looks for immediate "
            "relief, clear onboarding, credentialed expertise, and reassurance that a "
            "parent will be safe, dignified, and well-managed."
        ),
    ),
    PersonaJudge(
        persona_id="exhausted_spouse_caregiver",
        name="The Exhausted Spouse Caregiver",
        role="Co-resident partner",
        background=(
            "Older adult, typically 70+, living with a spouse and serving as primary "
            "caregiver out of love, duty, and habit."
        ),
        pain_points=[
            "Physical exhaustion from mobility help, bathing support, and nighttime wakefulness.",
            "Isolation and loss of identity or social life outside caregiving.",
            "Resistance to a nursing home, paired with the realization they cannot do it alone.",
            "Fear of long contracts or large financial commitments when they want a few hours of relief.",
        ],
        buying_triggers=[
            "A personal medical scare for the healthier spouse.",
            "Total physical or emotional burnout that makes their own health feel at risk.",
        ],
        search_intent=(
            "Relief-oriented and cautious. Searches for part-time, flexible respite "
            "support that provides a break without feeling like abandonment or an "
            "expensive inflexible contract."
        ),
    ),
    PersonaJudge(
        persona_id="veteran_advocate",
        name="The Veteran / Veteran's Advocate",
        role="Benefits navigator",
        background=(
            "Aging wartime veteran or adult child managing affairs for a veteran "
            "parent who needs daily living assistance."
        ),
        pain_points=[
            "Frustration with complex benefits systems and qualification rules.",
            "Desire for dignified aging in place that honors the veteran's service.",
            "Financial constraints that make private duty care difficult without earned benefits.",
        ],
        buying_triggers=[
            "Discovery that VA benefits such as Aid and Attendance can fund accredited in-home non-medical care.",
            "Rapid decline in mobility or independence that forces the household to use benefits.",
        ],
        search_intent=(
            "Trust- and qualification-driven. Looks for explicit confirmation that an "
            "agency is an approved provider, knows the paperwork, and respects veteran households."
        ),
    ),
    PersonaJudge(
        persona_id="post_rehab_transitioner",
        name="The Post-Rehab Transitioner",
        role="Short-term recovery patient",
        background=(
            "Independent older adult recently discharged or preparing for discharge "
            "after surgery, a cardiac procedure, mild stroke, or another temporary medical event."
        ),
        pain_points=[
            "Sudden loss of independence and frustration with physical limits.",
            "Anxiety about reinjury during recovery at home.",
            "Difficulty cooking, bathing, managing reminders, and getting to follow-up appointments.",
        ],
        buying_triggers=[
            "An imminent hospital or rehab discharge date with a requirement for a home care plan.",
        ],
        search_intent=(
            "Urgent, specific, and temporary. Looks for flexible short-term transition "
            "care focused on recovery support, reminders, transportation, and physical assistance."
        ),
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenRouter RSA audit optimization loop")
    parser.add_argument("--spec", type=Path, required=True, help="Path to the RSA spec file")
    parser.add_argument(
        "--program",
        type=Path,
        default=Path("rsa_spec_program.md"),
        help="Path to the mutator program file",
    )
    parser.add_argument(
        "--rubric",
        type=Path,
        default=Path("rsa_scoring_rubric.md"),
        help="Path to the locked scoring rubric file",
    )
    parser.add_argument("--tag", required=True, help="Run tag, used for branch and logs")
    parser.add_argument("--rounds", type=int, default=100, help="Maximum rounds to run")
    parser.add_argument(
        "--stale-limit",
        type=int,
        default=15,
        help="Stop after this many consecutive rejected rounds",
    )
    parser.add_argument(
        "--branch-prefix",
        default="rsaspecsearch",
        help="Git branch prefix for automated experiment branches",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".runs"),
        help="Directory for local run artifacts",
    )
    parser.add_argument(
        "--mutator-temperature",
        type=float,
        default=0.7,
        help="Temperature for the mutator model",
    )
    parser.add_argument(
        "--judge-temperature",
        type=float,
        default=0.2,
        help="Temperature for the judge model",
    )
    parser.add_argument(
        "--model-attempts",
        type=int,
        default=3,
        help="Maximum formatting retries per model call",
    )
    parser.add_argument(
        "--allowed-sections",
        nargs="+",
        help="Optional list of active section names the mutator may edit during this run",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Disable branch creation and commits",
    )
    parser.add_argument(
        "--search-policy",
        choices=SEARCH_POLICIES,
        default="classic",
        help="Search controller policy. Defaults to classic behavior.",
    )
    return parser.parse_args()


def load_spec(path: Path) -> str:
    return load_text_file(path, "RSA spec file")


def load_program(path: Path) -> str:
    return load_text_file(path, "Program file")


def parse_score_from_spec(text: str) -> float | None:
    match = SCORE_LINE_RE.search(text)
    if not match:
        return None
    return float(match.group(1))


def section_marker_pattern(section_name: str) -> str:
    marker = SECTION_MARKERS[section_name]
    return rf"(?m)^{re.escape(marker)}(?:\b.*)?$"


def parse_spec(text: str) -> ParsedSpec:
    positions: list[tuple[str, int]] = []
    for section_name in SECTION_ORDER:
        marker = SECTION_MARKERS[section_name]
        match = re.search(rf"(?m)^{re.escape(marker)}(?:\b.*)?$", text)
        if not match:
            raise SpecLoopError(f"Could not find section marker: {marker}")
        positions.append((section_name, match.start()))

    header = text[: positions[0][1]]
    sections: dict[str, str] = {}
    for index, (section_name, start_pos) in enumerate(positions):
        end_pos = positions[index + 1][1] if index + 1 < len(positions) else len(text)
        sections[section_name] = text[start_pos:end_pos]
    return ParsedSpec(header=header, sections=sections)


def normalize_header_for_compare(header: str) -> str:
    return SCORE_LINE_RE.sub("Current champion score: __SCORE__/100", header)


def pick_frontier_track(round_number: int) -> str:
    return FRONTIER_TRACKS[(round_number - 1) % len(FRONTIER_TRACKS)]


def choose_overall_track(frontier: dict[str, FrontierEntry]) -> str:
    best_track = FRONTIER_TRACKS[0]
    best_score = frontier[best_track].score
    for track in FRONTIER_TRACKS[1:]:
        score = frontier[track].score
        if score > best_score:
            best_track = track
            best_score = score
    return best_track


def choose_base_track(round_track: str, frontier: dict[str, FrontierEntry], overall_track: str) -> str:
    if round_track != "synthesis":
        return round_track
    candidate_tracks = ["synthesis", overall_track, "conservative", "differentiated"]
    best_track = candidate_tracks[0]
    best_score = frontier[best_track].score
    for track in candidate_tracks[1:]:
        score = frontier[track].score
        if score > best_score:
            best_track = track
            best_score = score
    return best_track


def render_frontier_snapshot(frontier: dict[str, FrontierEntry], overall_track: str) -> str:
    lines = []
    for track in FRONTIER_TRACKS:
        entry = frontier[track]
        marker = " (overall best)" if track == overall_track else ""
        lines.append(
            f"- {TRACK_LABELS[track]}: {format_score(entry.score)}/100 | "
            f"round {entry.source_round} | {entry.change_summary}{marker}"
        )
    return "\n".join(lines)


def recent_frontier_history(records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    accepted: list[str] = []
    rejected: list[str] = []
    for record in records:
        if record.get("kind") != "round":
            continue
        summary = str(record.get("change_summary", "")).strip()
        section = str(record.get("changed_section", "")).strip()
        track = str(record.get("track", "overall")).strip()
        total = record.get("candidate_score", record.get("champion_score"))
        rendered = (
            f"Round {record['round']} | {track} | {section} | {summary} | "
            f"{format_score(float(total))}/100"
        )
        if record.get("accepted"):
            accepted.append(rendered)
        else:
            rejected.append(rendered)
    return accepted, rejected


def render_persona_for_prompt(persona: PersonaJudge) -> str:
    pain_points = "\n".join(f"- {item}" for item in persona.pain_points)
    buying_triggers = "\n".join(f"- {item}" for item in persona.buying_triggers)
    return textwrap.dedent(
        f"""
        Persona: {persona.name}
        Role/background: {persona.role}. {persona.background}
        Pain points:
        {pain_points}
        Buying triggers:
        {buying_triggers}
        Search intent: {persona.search_intent}
        """
    ).strip()


def render_prior_persona_feedback(persona_judgements: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in persona_judgements:
        persona_name = str(item.get("persona_name", item.get("persona_id", "Unknown persona"))).strip()
        score = item.get("total_score")
        feedback = str(item.get("feedback", "")).strip()
        if not feedback:
            feedback = str(item.get("summary", "")).strip()
        score_text = ""
        if score is not None:
            try:
                score_text = f" ({format_score(float(score))}/100)"
            except (TypeError, ValueError):
                score_text = ""
        if feedback:
            lines.append(f"- {persona_name}{score_text}: {feedback}")
    return "\n".join(lines) if lines else "- None yet"


def latest_persona_feedback(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for record in reversed(records):
        persona_judgements = record.get("persona_judgements")
        if isinstance(persona_judgements, list) and persona_judgements:
            return [item for item in persona_judgements if isinstance(item, dict)]
    return []


def persona_judgements_from_raw(raw_response: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        return []
    persona_judgements = payload.get("persona_judgements")
    if not isinstance(persona_judgements, list):
        return []
    return [item for item in persona_judgements if isinstance(item, dict)]


def find_changed_sections(current_spec: str, candidate_spec: str) -> list[str]:
    current = parse_spec(current_spec)
    candidate = parse_spec(candidate_spec)
    changed = []
    for section_name in SECTION_ORDER:
        if current.sections[section_name] != candidate.sections[section_name]:
            changed.append(section_name)
    return changed


def splice_updated_section(current_spec: str, section_name: str, updated_section: str) -> str:
    if section_name not in SECTION_ORDER:
        raise SpecLoopError(f"Unknown section for splice: {section_name!r}")
    if not re.search(section_marker_pattern(section_name), updated_section):
        raise SpecLoopError(
            f"Updated section must include its own section marker: {SECTION_MARKERS[section_name]}"
        )
    parsed = parse_spec(current_spec)
    sections = dict(parsed.sections)
    sections[section_name] = updated_section.strip() + "\n\n"
    return parsed.header + "".join(sections[name] for name in SECTION_ORDER)


def split_editable_block(section_text: str) -> tuple[str, str]:
    match = re.search(rf"(?m)^{re.escape(EDITABLE_MARKER)}\s*$", section_text)
    if not match:
        raise SpecLoopError(f"Section is missing the `{EDITABLE_MARKER}` marker.")
    body_start = match.end()
    if body_start < len(section_text) and section_text[body_start] == "\n":
        body_start += 1
    prefix = section_text[:body_start]
    body = section_text[body_start:]
    if not body.strip():
        raise SpecLoopError("Editable challenger block is empty.")
    return prefix, body


def extract_labeled_bullets(section_text: str, label: str) -> list[str]:
    pattern = rf"(?m)^\s*{re.escape(label)}:\s*\n(?P<body>(?:\s*-\s+[^\n]+\n)+)"
    match = re.search(pattern, section_text)
    if not match:
        return []
    return re.findall(r"(?m)^\s*-\s+(.+?)\s*$", match.group("body"))


def extract_single_line_field(block_text: str, label: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(label)}:\s*(.+?)\s*$", block_text)
    if not match:
        return None
    return match.group(1).strip()


def collect_copy_text(headlines: list[str], descriptions: list[str], hypothesis: str, why_lines: list[str]) -> str:
    return "\n".join([hypothesis, *headlines, *descriptions, *why_lines])


def detect_themes(headline: str) -> set[str]:
    lowered = headline.lower()
    themes = {
        theme
        for theme, needles in THEME_KEYWORDS.items()
        if any(needle in lowered for needle in needles)
    }
    if not themes:
        themes.add("other")
    return themes


def find_forbidden_terms(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(term for term in FORBIDDEN_COPY_TERMS if term in lowered)


def validate_editable_challenger(section_name: str, section_text: str) -> list[str]:
    errors: list[str] = []
    if section_name not in ACTIVE_SECTIONS:
        return errors

    try:
        _prefix, body = split_editable_block(section_text)
    except SpecLoopError as exc:
        return [str(exc)]

    hypothesis = extract_single_line_field(body, "Hypothesis")
    if not hypothesis:
        errors.append("Editable challenger is missing a non-empty 'Hypothesis' line.")

    target_query_themes = extract_labeled_bullets(body, "Target query themes")
    if len(target_query_themes) < 3:
        errors.append("Editable challenger needs at least 3 target query themes.")

    fixed_url = extract_single_line_field(body, "Fixed recommended URL")
    expected_url = ALLOWED_SECTION_URLS[section_name]
    if fixed_url is None:
        errors.append("Editable challenger is missing 'Fixed recommended URL'.")
    elif fixed_url.strip("`") != expected_url:
        errors.append(
            f"Fixed recommended URL for {section_name} must remain {expected_url!r}, not {fixed_url!r}."
        )

    headlines = extract_labeled_bullets(body, "Headlines")
    descriptions = extract_labeled_bullets(body, "Descriptions")
    why_lines = extract_labeled_bullets(body, "Why this should beat current live ads")

    if len(headlines) != 15:
        errors.append(f"{section_name} must list exactly 15 headlines; found {len(headlines)}.")
    if len(descriptions) != 4:
        errors.append(f"{section_name} must list exactly 4 descriptions; found {len(descriptions)}.")
    if len(why_lines) < 2:
        errors.append(f"{section_name} needs at least 2 rationale bullets under 'Why this should beat current live ads'.")

    if len(set(headlines)) != len(headlines):
        errors.append(f"{section_name} cannot include duplicate headlines.")
    if len(set(descriptions)) != len(descriptions):
        errors.append(f"{section_name} cannot include duplicate descriptions.")

    for headline in headlines:
        if len(headline) > 30:
            errors.append(f"Headline exceeds 30 characters: {headline!r}")
    for description in descriptions:
        if len(description) > 90:
            errors.append(f"Description exceeds 90 characters: {description!r}")

    copy_text = collect_copy_text(
        headlines=headlines,
        descriptions=descriptions,
        hypothesis=hypothesis or "",
        why_lines=why_lines,
    )
    if re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", copy_text):
        errors.append("Ad copy must not contain phone numbers.")
    if "http://" in copy_text.lower() or "https://" in copy_text.lower():
        errors.append("Ad copy must not contain raw URLs.")

    forbidden_terms = find_forbidden_terms(copy_text)
    if forbidden_terms:
        errors.append(
            f"Ad copy contains off-strategy or policy-risk terms: {', '.join(forbidden_terms)}."
        )

    themes = set()
    for headline in headlines:
        themes.update(detect_themes(headline))
    if len(themes) < 5:
        errors.append(
            f"Headline set must cover at least 5 distinct themes; detected {len(themes)} ({sorted(themes)})."
        )

    return errors


def validate_candidate_spec(
    *,
    current_spec: str,
    candidate_spec: str,
    declared_section: str,
    current_score: float,
    allowed_sections: list[str] | None = None,
) -> tuple[str, list[str]]:
    errors: list[str] = []
    if declared_section not in ACTIVE_SECTIONS:
        errors.append(f"Changed section must be one of {ACTIVE_SECTIONS}; got {declared_section!r}.")
        return candidate_spec, errors
    if allowed_sections is not None and declared_section not in allowed_sections:
        errors.append(
            f"Changed section must be one of {allowed_sections} for this run; got {declared_section!r}."
        )
        return candidate_spec, errors

    try:
        normalized_candidate = replace_current_champion_score(candidate_spec, current_score)
        current = parse_spec(current_spec)
        candidate = parse_spec(normalized_candidate)
    except SpecLoopError as exc:
        errors.append(str(exc))
        return candidate_spec, errors

    if normalize_header_for_compare(current.header) != normalize_header_for_compare(candidate.header):
        errors.append("Only the editable sections may change; the header changed.")

    changed_sections = find_changed_sections(current_spec, normalized_candidate)
    if changed_sections != [declared_section]:
        errors.append(
            f"Exactly one editable section may change. Declared={declared_section!r}, changed={changed_sections}."
        )

    for section_name in ACTIVE_SECTIONS:
        try:
            current_prefix, _ = split_editable_block(current.sections[section_name])
            candidate_prefix, _ = split_editable_block(candidate.sections[section_name])
        except SpecLoopError as exc:
            errors.append(str(exc))
            continue
        if current_prefix != candidate_prefix:
            errors.append(
                f"Locked evidence changed inside {section_name}. Only the editable challenger block may change."
            )
        errors.extend(validate_editable_challenger(section_name, candidate.sections[section_name]))

    return normalized_candidate, errors


def parse_judgement(raw_text: str) -> Judgement:
    payload_text = extract_json_object(raw_text)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise SpecLoopError(f"Judge returned invalid JSON: {exc}") from exc

    try:
        scores_input = payload["scores"]
        rationales_input = payload["category_rationales"]
    except KeyError as exc:
        raise SpecLoopError(f"Judge response is missing required field: {exc.args[0]}") from exc

    if not isinstance(scores_input, dict):
        raise SpecLoopError("'scores' must be an object.")
    if not isinstance(rationales_input, dict):
        raise SpecLoopError("'category_rationales' must be an object.")

    scores: dict[str, float] = {}
    rationales: dict[str, str] = {}
    for key, max_score in SCORE_CATEGORY_MAXES.items():
        if key not in scores_input:
            raise SpecLoopError(f"Judge score is missing category: {key}")
        if key not in rationales_input:
            raise SpecLoopError(f"Judge rationale is missing category: {key}")
        score_value = float(scores_input[key])
        if not (0.0 <= score_value <= max_score):
            raise SpecLoopError(
                f"Judge score for {key} must be within 0..{max_score}, got {score_value}."
            )
        scores[key] = score_value
        rationales[key] = str(rationales_input[key]).strip()

    total_score = float(payload["total_score"])
    computed_total = sum(scores.values())
    if not math.isclose(total_score, computed_total, abs_tol=0.5):
        raise SpecLoopError(
            f"Judge total score {total_score} does not match category sum {computed_total}."
        )

    violations = payload.get("violations", [])
    if not isinstance(violations, list):
        raise SpecLoopError("'violations' must be an array.")

    private_signal = normalize_private_judge_signal(payload)
    return Judgement(
        constraint_pass=bool(payload["constraint_pass"]),
        violations=[str(item) for item in violations],
        scores=scores,
        category_rationales=rationales,
        total_score=round(total_score, 2),
        summary=str(payload.get("summary", "")).strip(),
        raw_response=raw_text,
        private_feedback=private_signal.private_feedback,
        socratic_questions=private_signal.socratic_questions,
        uncertainty=private_signal.uncertainty,
        risk_tags=private_signal.risk_tags,
        novelty_score=private_signal.novelty_score,
    )


def default_frontier(spec_text: str, champion_score: float) -> dict[str, FrontierEntry]:
    normalized_spec = replace_current_champion_score(spec_text, champion_score)
    return {
        track: FrontierEntry(
            spec_text=normalized_spec,
            score=champion_score,
            source_round=0,
            changed_section="baseline",
            change_summary="baseline",
        )
        for track in FRONTIER_TRACKS
    }


def write_frontier(
    run_dir: Path,
    frontier: dict[str, FrontierEntry],
    overall_track: str,
) -> None:
    frontier_dir = run_dir / "frontier"
    frontier_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "overall_track": overall_track,
        "tracks": {},
    }
    for track in FRONTIER_TRACKS:
        entry = frontier[track]
        spec_path = frontier_dir / f"{track}.md"
        spec_text = replace_current_champion_score(entry.spec_text, entry.score)
        write_text(spec_path, spec_text)
        payload["tracks"][track] = {
            "score": entry.score,
            "source_round": entry.source_round,
            "changed_section": entry.changed_section,
            "change_summary": entry.change_summary,
            "spec_path": str(spec_path.relative_to(run_dir)),
        }
    write_text(run_dir / "frontier.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_frontier(run_dir: Path) -> tuple[dict[str, FrontierEntry] | None, str | None]:
    metadata_path = run_dir / "frontier.json"
    if not metadata_path.exists():
        return None, None
    payload = json.loads(load_text_file(metadata_path, "RSA frontier metadata"))
    tracks_payload = payload.get("tracks")
    if not isinstance(tracks_payload, dict):
        raise SpecLoopError("RSA frontier metadata is missing the 'tracks' object.")

    frontier: dict[str, FrontierEntry] = {}
    for track in FRONTIER_TRACKS:
        track_payload = tracks_payload.get(track)
        if not isinstance(track_payload, dict):
            raise SpecLoopError(f"RSA frontier metadata is missing track {track!r}.")
        spec_rel = track_payload.get("spec_path")
        if not spec_rel:
            raise SpecLoopError(f"RSA frontier metadata for {track!r} is missing 'spec_path'.")
        spec_text = load_text_file(run_dir / spec_rel, f"RSA frontier spec for {track}")
        frontier[track] = FrontierEntry(
            spec_text=spec_text,
            score=float(track_payload["score"]),
            source_round=int(track_payload.get("source_round", 0)),
            changed_section=str(track_payload.get("changed_section", "baseline")),
            change_summary=str(track_payload.get("change_summary", "baseline")),
        )

    overall_track = str(payload.get("overall_track", "")).strip() or choose_overall_track(frontier)
    if overall_track not in FRONTIER_TRACKS:
        overall_track = choose_overall_track(frontier)
    return frontier, overall_track


def ensure_frontier(
    *,
    run_dir: Path,
    current_spec: str,
    champion_score: float,
) -> tuple[dict[str, FrontierEntry], str]:
    frontier, overall_track = load_frontier(run_dir)
    if frontier is not None and overall_track is not None:
        return frontier, overall_track
    frontier = default_frontier(current_spec, champion_score)
    overall_track = choose_overall_track(frontier)
    write_frontier(run_dir, frontier, overall_track)
    return frontier, overall_track


def build_mutator_prompt(
    *,
    program_text: str,
    target_file_name: str,
    spec_text: str,
    champion_score: float,
    track_name: str,
    track_score: float,
    base_track_name: str,
    frontier_snapshot: str,
    round_number: int,
    accepted_summaries: list[str],
    recent_rejections: list[str],
    prior_persona_feedback: list[dict[str, Any]] | None = None,
    allowed_sections: list[str] | None = None,
    search_decision: SearchDecision | None = None,
    retry_feedback: str | None = None,
) -> list[dict[str, str]]:
    accepted_block = "\n".join(f"- {item}" for item in accepted_summaries[-8:]) or "- None yet"
    rejected_block = "\n".join(f"- {item}" for item in recent_rejections[-5:]) or "- None yet"
    persona_feedback_block = render_prior_persona_feedback(prior_persona_feedback or [])
    search_block = ""
    if search_decision is not None:
        banned_block = "\n".join(f"- {item}" for item in search_decision.banned_signatures) or "- None"
        search_block = textwrap.dedent(
            f"""

            Socratic search directive:
            - Search track: {search_decision.track}
            - Exploration level: {search_decision.exploration_level}
            - Abstract question to answer through the candidate: {search_decision.socratic_prompt}
            - Hidden feedback policy: {search_decision.hidden_feedback_policy}
            - Avoid near-duplicate signatures:
            {banned_block}

            Treat the abstract question as a search prompt, not as judge feedback. Do not infer or imitate private judge critique.
            """
        ).rstrip()
        rejected_block = "- Hidden in this policy to avoid over-narrowing the next search step."
    retry_block = ""
    if retry_feedback:
        retry_block = f"\nYour previous attempt failed validation for this reason:\n{retry_feedback}\n"
    allowed_block = ""
    if allowed_sections is not None:
        allowed_block = (
            "\nAllowed sections for this run:\n- "
            + "\n- ".join(allowed_sections)
            + "\nDo not edit any other section.\n"
        )

    system_prompt = textwrap.dedent(
        """
        Follow the provided program file as your standing instructions.
        You may only edit the target RSA spec file supplied by the runner.
        Return exactly this format:
        <mutation>
        {"changed_section":"Core Non-Medical Home Care","change_summary":"One sentence summary."}
        </mutation>
        <updated_section>
        FULL UPDATED SECTION TEXT HERE, INCLUDING ITS SECTION MARKER
        </updated_section>
        """
    ).strip()

    user_prompt = textwrap.dedent(
        f"""
        Target file to edit: {target_file_name}

        Program file:
        <program>
        {program_text}
        </program>

        Goal: produce the strongest promotion-worthy v2 RSA hypothesis for the two active reset ad groups using proxy signals because conversion tracking is unreliable and impressions are sparse.
        Current champion score: {format_score(champion_score)}/100
        Frontier track for this round: {TRACK_LABELS[track_name]}
        Track strategy: {TRACK_STRATEGIES[track_name]}
        Score to beat for this track: {format_score(track_score)}/100
        Base track used for this round: {TRACK_LABELS[base_track_name]}
        Round: {round_number}

        Current frontier:
        {frontier_snapshot}

        Accepted improvements so far:
        {accepted_block}

        Recent rejected ideas:
        {rejected_block}

        Prior-round persona judge feedback:
        {persona_feedback_block}
        {search_block}
        {allowed_block}
        {retry_block}
        Runner requirements:
        - Keep the "Current champion score" line unchanged. The runner will update it if you win.
        - Return only the single updated section, including its section marker.
        - Do not reprint the whole file.
        - Do not change locked evidence or locked notes.

        Current spec:
        <spec>
        {spec_text}
        </spec>
        """
    ).strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_judge_prompt(
    *,
    spec_text: str,
    rubric_text: str,
    champion_score: float,
    persona: PersonaJudge | None = None,
    search_policy: str = "classic",
    retry_feedback: str | None = None,
) -> list[dict[str, str]]:
    retry_block = f"\nYour previous response failed parsing for this reason:\n{retry_feedback}\n" if retry_feedback else ""
    persona_block = render_persona_for_prompt(persona) if persona is not None else "Persona: General strict RSA evaluator"
    private_shape = textwrap.dedent(
        """
          "private_feedback": "specific feedback from this persona judge for the next draft",
        """
    )
    private_instructions = textwrap.dedent(
        """
        Also include private_feedback: concise, concrete feedback from this persona's perspective that the next draft should use.
        """
    )
    if search_policy == SOCRATIC_SEARCH_POLICY:
        private_shape = textwrap.dedent(
            """
              "private_feedback": "specific feedback from this persona judge for the next draft",
              "socratic_questions": ["abstract search question"],
              "uncertainty": 0,
              "risk_tags": ["..."],
              "novelty_score": 0,
            """
        )
        private_instructions = textwrap.dedent(
            """
            Also include private controller metadata:
            - private_feedback: concise, concrete feedback from this persona's perspective that the next draft should use.
            - socratic_questions: 1-3 abstract questions that open search space instead of prescribing copy changes.
            - uncertainty: 0..1 confidence uncertainty in this judgement.
            - risk_tags: short labels for strategic/policy/fit risks.
            - novelty_score: 0..1 estimate of whether the candidate explores a meaningfully distinct on-strategy hypothesis.
            """
        )
    system_prompt = textwrap.dedent(
        """
        You are a strict Google Ads RSA judge scoring a low-volume, document-first challenger spec.
        Score the candidate independently against the rubric below from the assigned home-care persona's perspective.
        Return JSON only.

        Required JSON shape:
        {
          "constraint_pass": true,
          "violations": ["..."],
          "scores": {
            "query_message_fit": 0,
            "ctr_lift_vs_live_comparators": 0,
            "click_quality_protection": 0,
            "trust_private_pay_specificity": 0,
            "landing_page_fit": 0,
            "rsa_diversity_strength": 0,
            "policy_brand_safety": 0
          },
          "category_rationales": {
            "query_message_fit": "brief rationale",
            "ctr_lift_vs_live_comparators": "brief rationale",
            "click_quality_protection": "brief rationale",
            "trust_private_pay_specificity": "brief rationale",
            "landing_page_fit": "brief rationale",
            "rsa_diversity_strength": "brief rationale",
            "policy_brand_safety": "brief rationale"
          },
__PRIVATE_SHAPE__
          "total_score": 0,
          "summary": "brief summary"
        }
        """
    ).replace("__PRIVATE_SHAPE__", private_shape).strip()
    user_prompt = textwrap.dedent(
        f"""
        Candidate spec to score:
        <spec>
        {spec_text}
        </spec>

        Assigned persona judge:
        <persona>
        {persona_block}
        </persona>

        Locked scoring rubric:
        <rubric>
        {rubric_text}
        </rubric>

        Current champion score threshold: {format_score(champion_score)}/100
        {retry_block}
        Use these rubric maxima:
        - query_message_fit: 20
        - ctr_lift_vs_live_comparators: 20
        - click_quality_protection: 15
        - trust_private_pay_specificity: 15
        - landing_page_fit: 10
        - rsa_diversity_strength: 10
        - policy_brand_safety: 10

        Because conversion tracking is broken, weigh CTR, clicks, spend, ad strength, query quality, and landing-page fit more heavily than raw conversion totals.
        Treat live comparators and any carried-forward contextual inputs as soft priors and tie-breakers, not mandatory wording or proof that tiny paraphrases are better.
        Reward useful differentiated hypotheses when they stay tightly on-strategy and commercially relevant.
        Keep rationales short and concrete.
        {private_instructions}
        """
    ).strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_mutator(
    *,
    client: OpenRouterClient,
    model: str,
    reasoning: dict[str, Any] | None,
    program_text: str,
    target_file_name: str,
    spec_text: str,
    champion_score: float,
    track_name: str,
    track_score: float,
    base_track_name: str,
    frontier_snapshot: str,
    round_number: int,
    accepted_summaries: list[str],
    recent_rejections: list[str],
    allowed_sections: list[str] | None,
    search_decision: SearchDecision | None,
    attempts: int,
    temperature: float,
) -> Mutation:
    retry_feedback: str | None = None
    last_response = ""
    for _ in range(attempts):
        messages = build_mutator_prompt(
            program_text=program_text,
            target_file_name=target_file_name,
            spec_text=spec_text,
            champion_score=champion_score,
            track_name=track_name,
            track_score=track_score,
            base_track_name=base_track_name,
            frontier_snapshot=frontier_snapshot,
            round_number=round_number,
            accepted_summaries=accepted_summaries,
            recent_rejections=recent_rejections,
            allowed_sections=allowed_sections,
            search_decision=search_decision,
            retry_feedback=retry_feedback,
        )
        try:
            raw_response = client.complete(
                model=model,
                messages=messages,
                temperature=temperature,
                reasoning=reasoning,
            )
        except SpecLoopError as exc:
            retry_feedback = str(exc)
            last_response = f"<client_error>{exc}</client_error>"
            continue
        try:
            return parse_mutation(raw_response)
        except SpecLoopError as exc:
            retry_feedback = str(exc)
            last_response = raw_response
    raise SpecLoopError(
        f"Mutator failed after {attempts} attempts. Last error: {retry_feedback}\n"
        f"Last response:\n{last_response}"
    )


def serialize_persona_judgements(persona_judgements: list[PersonaJudgement]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for item in persona_judgements:
        judgement = item.judgement
        serialized.append(
            {
                "persona_id": item.persona.persona_id,
                "persona_name": item.persona.name,
                "role": item.persona.role,
                "constraint_pass": judgement.constraint_pass,
                "violations": judgement.violations,
                "scores": judgement.scores,
                "category_rationales": judgement.category_rationales,
                "total_score": judgement.total_score,
                "feedback": judgement.private_feedback,
                "summary": judgement.summary,
                "socratic_questions": judgement.socratic_questions or [],
                "uncertainty": judgement.uncertainty,
                "risk_tags": judgement.risk_tags or [],
                "novelty_score": judgement.novelty_score,
            }
        )
    return serialized


def aggregate_persona_judgements(persona_judgements: list[PersonaJudgement]) -> Judgement:
    if not persona_judgements:
        raise SpecLoopError("Persona council returned no judgements.")

    count = len(persona_judgements)
    scores = {
        key: round(sum(item.judgement.scores[key] for item in persona_judgements) / count, 2)
        for key in SCORE_CATEGORY_MAXES
    }
    rationales = {
        key: " | ".join(
            f"{item.persona.name}: {item.judgement.category_rationales[key]}"
            for item in persona_judgements
        )
        for key in SCORE_CATEGORY_MAXES
    }
    violations: list[str] = []
    summaries: list[str] = []
    feedback_items: list[str] = []
    socratic_questions: list[str] = []
    risk_tags: list[str] = []
    uncertainty = 0.0
    novelty_score = 0.0
    for item in persona_judgements:
        judgement = item.judgement
        violations.extend(f"{item.persona.name}: {violation}" for violation in judgement.violations)
        if judgement.summary:
            summaries.append(f"{item.persona.name}: {judgement.summary}")
        if judgement.private_feedback:
            feedback_items.append(f"{item.persona.name}: {judgement.private_feedback}")
        socratic_questions.extend(judgement.socratic_questions or [])
        risk_tags.extend(judgement.risk_tags or [])
        uncertainty += judgement.uncertainty
        novelty_score += judgement.novelty_score

    raw_payload = {
        "council_size": count,
        "weighting": "equal",
        "constraint_pass": all(item.judgement.constraint_pass for item in persona_judgements),
        "violations": violations,
        "scores": scores,
        "category_rationales": rationales,
        "total_score": round(sum(item.judgement.total_score for item in persona_judgements) / count, 2),
        "summary": " | ".join(summaries),
        "persona_judgements": serialize_persona_judgements(persona_judgements),
    }
    return Judgement(
        constraint_pass=bool(raw_payload["constraint_pass"]),
        violations=violations,
        scores=scores,
        category_rationales=rationales,
        total_score=float(raw_payload["total_score"]),
        summary=str(raw_payload["summary"]),
        raw_response=json.dumps(raw_payload, indent=2),
        private_feedback="\n".join(feedback_items),
        socratic_questions=socratic_questions[:3],
        uncertainty=round(uncertainty / count, 2),
        risk_tags=list(dict.fromkeys(risk_tags))[:8],
        novelty_score=round(novelty_score / count, 2),
    )


def call_judge(
    *,
    client: OpenRouterClient,
    model: str,
    reasoning: dict[str, Any] | None,
    spec_text: str,
    rubric_text: str,
    champion_score: float,
    attempts: int,
    temperature: float,
    search_policy: str = "classic",
) -> Judgement:
    persona_judgements: list[PersonaJudgement] = []
    failures: list[str] = []
    for persona in HOME_CARE_PERSONAS:
        retry_feedback: str | None = None
        last_response = ""
        for _ in range(attempts):
            messages = build_judge_prompt(
                spec_text=spec_text,
                rubric_text=rubric_text,
                champion_score=champion_score,
                persona=persona,
                search_policy=search_policy,
                retry_feedback=retry_feedback,
            )
            try:
                raw_response = client.complete(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    reasoning=reasoning,
                )
            except SpecLoopError as exc:
                retry_feedback = str(exc)
                last_response = f"<client_error>{exc}</client_error>"
                continue
            try:
                persona_judgements.append(
                    PersonaJudgement(persona=persona, judgement=parse_judgement(raw_response))
                )
                break
            except SpecLoopError as exc:
                retry_feedback = str(exc)
                last_response = raw_response
        else:
            failures.append(
                f"{persona.name} failed after {attempts} attempts. "
                f"Last error: {retry_feedback}\nLast response:\n{last_response}"
            )

    if failures:
        raise SpecLoopError("Persona council judge failed:\n" + "\n\n".join(failures))
    return aggregate_persona_judgements(persona_judgements)


def baseline_if_needed(
    *,
    spec_path: Path,
    run_dir: Path,
    records_path: Path,
    current_spec: str,
    judge: OpenRouterClient,
    judge_model: str,
    judge_reasoning: dict[str, Any] | None,
    rubric_text: str,
    judge_attempts: int,
    judge_temperature: float,
    git_enabled: bool,
    repo_root: Path,
    spec_relative_path: str,
    tag: str,
) -> tuple[str, float, list[dict[str, Any]]]:
    records = load_jsonl(records_path)
    if records:
        champion_score = float(records[-1]["champion_score"])
        return current_spec, champion_score, records

    print("Scoring baseline...")
    baseline_judgement = call_judge(
        client=judge,
        model=judge_model,
        reasoning=judge_reasoning,
        spec_text=current_spec,
        rubric_text=rubric_text,
        champion_score=0.0,
        attempts=judge_attempts,
        temperature=judge_temperature,
    )
    baseline_score = baseline_judgement.total_score
    normalized_spec = replace_current_champion_score(current_spec, baseline_score)
    if normalized_spec != current_spec:
        write_text(spec_path, normalized_spec)

    commit_sha = None
    if git_enabled:
        commit_message = f"rsaspec: baseline {tag} ({format_score(baseline_score)}/100)"
        commit_sha = git_commit_path(repo_root, spec_relative_path, commit_message)

    write_text(run_dir / "winner.md", normalized_spec)
    write_text(run_dir / "final_report.md", "")
    write_text(run_dir / "baseline_judgement.json", baseline_judgement.raw_response)

    baseline_record = {
        "kind": "baseline",
        "round": 0,
        "accepted": True,
        "constraint_pass": baseline_judgement.constraint_pass,
        "violations": baseline_judgement.violations,
        "scores": baseline_judgement.scores,
        "category_rationales": baseline_judgement.category_rationales,
        "persona_judgements": persona_judgements_from_raw(baseline_judgement.raw_response),
        "candidate_score": baseline_score,
        "champion_score": baseline_score,
        "change_summary": "baseline",
        "changed_section": "baseline",
        "summary": baseline_judgement.summary,
        "commit": commit_sha,
        "timestamp": int(time.time()),
    }
    append_jsonl(records_path, baseline_record)
    return normalized_spec, baseline_score, [baseline_record]


def build_final_report(
    *,
    tag: str,
    overall_spec_text: str,
    champion_score: float,
    overall_track: str,
    frontier: dict[str, FrontierEntry],
    rounds_run: int,
    stale_count: int,
    accepted_records: list[dict[str, Any]],
    search_policy: str = "classic",
    archived_candidates: int = 0,
) -> str:
    top_changes = sorted(
        accepted_records,
        key=lambda record: float(record["candidate_score"]) - float(record["score_before"]),
        reverse=True,
    )[:3]
    lines = [
        f"# RSA Specsearch Report: {tag}",
        "",
        f"Final overall best: {TRACK_LABELS[overall_track]} | {format_score(champion_score)}/100",
        f"Rounds completed: {rounds_run}",
        f"Accepted improvements: {len(accepted_records)}",
        f"Ending stale count: {stale_count}",
        f"Search policy: {search_policy}",
        f"Archived search candidates: {archived_candidates}",
        "",
        "## Frontier tracks",
    ]
    for track in FRONTIER_TRACKS:
        entry = frontier[track]
        lines.append(
            f"- {TRACK_LABELS[track]}: {format_score(entry.score)}/100 | "
            f"round {entry.source_round} | {entry.change_summary}"
        )

    lines.extend(
        [
            "",
            "## Top 3 accepted challenger changes",
        ]
    )
    if top_changes:
        for index, record in enumerate(top_changes, start=1):
            delta = float(record["candidate_score"]) - float(record["score_before"])
            lines.append(
                f"{index}. {record.get('track', 'overall')}: {record['changed_section']} | "
                f"{record['change_summary']} (+{delta:.1f})"
            )
    else:
        lines.append("1. No accepted improvements yet.")

    lines.extend(
        [
            "",
            "## Overall winning version",
            "```md",
            overall_spec_text.rstrip(),
            "```",
            "",
        ]
    )
    for track in FRONTIER_TRACKS:
        lines.extend(
            [
                f"## {TRACK_LABELS[track]} candidate",
                "```md",
                frontier[track].spec_text.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    allowed_sections = list(args.allowed_sections) if args.allowed_sections else list(ACTIVE_SECTIONS)
    invalid_sections = [item for item in allowed_sections if item not in ACTIVE_SECTIONS]
    if invalid_sections:
        raise SpecLoopError(
            f"--allowed-sections contains invalid section names: {invalid_sections}. "
            f"Valid sections: {ACTIVE_SECTIONS}"
        )

    spec_path = args.spec.resolve()
    repo_root = get_repo_root(spec_path)
    spec_relative_path = os.path.relpath(spec_path, repo_root)
    program_path = args.program if args.program.is_absolute() else (repo_root / args.program)
    rubric_path = args.rubric if args.rubric.is_absolute() else (repo_root / args.rubric)

    load_dotenv(repo_root / ".env")
    program_text = load_program(program_path)
    rubric_text = load_text_file(rubric_path, "Rubric file")

    if not args.no_git:
        ensure_git_repo(repo_root)
        branch_name = f"{args.branch_prefix}/{args.tag}"
        ensure_git_branch(repo_root, branch_name)

    api_key = require_env("OPENROUTER_API_KEY")
    mutator_model = require_env("OPENROUTER_MUTATOR_MODEL")
    judge_model = require_env("OPENROUTER_JUDGE_MODEL")
    mutator_reasoning = get_reasoning_config("OPENROUTER_MUTATOR_REASONING_EFFORT")
    judge_reasoning = get_reasoning_config("OPENROUTER_JUDGE_REASONING_EFFORT")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    client = OpenRouterClient(api_key=api_key, base_url=base_url)

    run_dir = (repo_root / args.output_dir / args.tag).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    records_path = run_dir / "rounds.jsonl"
    write_text(run_dir / "program.md", program_text)
    write_text(run_dir / "rubric.md", rubric_text)

    current_spec = load_spec(spec_path)
    current_spec, champion_score, _records = baseline_if_needed(
        spec_path=spec_path,
        run_dir=run_dir,
        records_path=records_path,
        current_spec=current_spec,
        judge=client,
        judge_model=judge_model,
        judge_reasoning=judge_reasoning,
        rubric_text=rubric_text,
        judge_attempts=args.model_attempts,
        judge_temperature=args.judge_temperature,
        git_enabled=not args.no_git,
        repo_root=repo_root,
        spec_relative_path=spec_relative_path,
        tag=args.tag,
    )
    frontier, overall_track = ensure_frontier(
        run_dir=run_dir,
        current_spec=current_spec,
        champion_score=champion_score,
    )
    current_spec = frontier[overall_track].spec_text
    champion_score = frontier[overall_track].score

    start_round, champion_score, stale_count = load_resume_state(load_jsonl(records_path))
    overall_track = choose_overall_track(frontier)
    champion_score = frontier[overall_track].score
    current_spec = frontier[overall_track].spec_text
    if not math.isclose(
        parse_score_from_spec(current_spec) or champion_score,
        champion_score,
        abs_tol=0.2,
    ):
        raise SpecLoopError(
            "Current spec score line does not match the logged champion score. "
            "Reset the file or use a new tag."
        )

    total_rounds_run = start_round - 1
    records = load_jsonl(records_path)
    accepted_summaries, rejected_summaries = recent_frontier_history(records)
    prior_persona_feedback = latest_persona_feedback(records)
    search_archive_path = run_dir / "search_archive.json"
    search_archive = load_search_archive(search_archive_path)

    for round_number in range(start_round, args.rounds + 1):
        if stale_count >= args.stale_limit:
            print(f"Stopping early after {stale_count} consecutive rejected rounds.")
            break

        round_track = pick_frontier_track(round_number)
        base_track = choose_base_track(round_track, frontier, overall_track)
        track_score = frontier[round_track].score
        base_score = frontier[base_track].score
        base_spec = frontier[base_track].spec_text
        base_candidate_id = f"{base_track}:round-{frontier[base_track].source_round}"
        search_decision = build_search_decision(
            policy=args.search_policy,
            round_number=round_number,
            stale_count=stale_count,
            archive=search_archive,
            base_candidate_id=base_candidate_id,
        )
        frontier_snapshot = render_frontier_snapshot(frontier, overall_track)
        print(
            f"Round {round_number}/{args.rounds} | track {round_track} "
            f"{format_score(track_score)}/100 | overall {TRACK_LABELS[overall_track]} "
            f"{format_score(champion_score)}/100 | stale {stale_count}/{args.stale_limit}"
        )
        try:
            mutation = call_mutator(
                client=client,
                model=mutator_model,
                reasoning=mutator_reasoning,
                program_text=program_text,
                target_file_name=spec_path.name,
                spec_text=base_spec,
                champion_score=base_score,
                track_name=round_track,
                track_score=track_score,
                base_track_name=base_track,
                frontier_snapshot=frontier_snapshot,
                round_number=round_number,
                accepted_summaries=accepted_summaries,
                recent_rejections=rejected_summaries,
                prior_persona_feedback=prior_persona_feedback,
                allowed_sections=allowed_sections,
                search_decision=search_decision,
                attempts=args.model_attempts,
                temperature=args.mutator_temperature,
            )
        except SpecLoopError as exc:
            stale_count += 1
            candidate_path, judgement_path, mutation_path = persist_round_artifacts(
                run_dir=run_dir,
                round_number=round_number,
                mutation_raw=str(exc),
                candidate_spec=None,
                judgement_raw=None,
            )
            record = {
                "kind": "round",
                "round": round_number,
                "accepted": False,
                "track": round_track,
                "base_track": base_track,
                "changed_section": "model_error",
                "change_summary": "Mutator failed to return a usable section after retries.",
                "score_before": track_score,
                "track_score_before": track_score,
                "track_score_after": track_score,
                "overall_score_before": champion_score,
                "candidate_score": track_score,
                "champion_score": champion_score,
                "constraint_pass": False,
                "violations": [str(exc)],
                "summary": "Rejected because the mutator/model call failed after retries.",
                "mutation_path": mutation_path,
                "candidate_path": candidate_path,
                "judgement_path": judgement_path,
                "timestamp": int(time.time()),
            }
            append_jsonl(records_path, record)
            rejected_summaries.append(
                f"Round {round_number} | model_error | mutator failed | {format_score(champion_score)}/100"
            )
            print(f"  rejected: {exc}")
            total_rounds_run = round_number
            continue

        try:
            candidate_spec = splice_updated_section(
                current_spec=base_spec,
                section_name=mutation.changed_section,
                updated_section=mutation.updated_section,
            )
        except SpecLoopError as exc:
            stale_count += 1
            candidate_path, judgement_path, mutation_path = persist_round_artifacts(
                run_dir=run_dir,
                round_number=round_number,
                mutation_raw=mutation.raw_response,
                candidate_spec=None,
                judgement_raw=None,
            )
            record = {
                "kind": "round",
                "round": round_number,
                "accepted": False,
                "track": round_track,
                "base_track": base_track,
                "changed_section": mutation.changed_section,
                "change_summary": mutation.change_summary,
                "score_before": track_score,
                "track_score_before": track_score,
                "track_score_after": track_score,
                "overall_score_before": champion_score,
                "candidate_score": track_score,
                "champion_score": champion_score,
                "constraint_pass": False,
                "violations": [str(exc)],
                "summary": "Rejected before judging because the returned section could not be spliced into the spec.",
                "mutation_path": mutation_path,
                "candidate_path": candidate_path,
                "judgement_path": judgement_path,
                "timestamp": int(time.time()),
            }
            append_jsonl(records_path, record)
            rejected_summaries.append(
                f"Round {round_number} | {mutation.changed_section} | {mutation.change_summary} | invalid"
            )
            print(f"  rejected: {exc}")
            total_rounds_run = round_number
            continue

        normalized_candidate, validation_errors = validate_candidate_spec(
            current_spec=base_spec,
            candidate_spec=candidate_spec,
            declared_section=mutation.changed_section,
            current_score=base_score,
            allowed_sections=allowed_sections,
        )
        candidate_path, judgement_path, mutation_path = persist_round_artifacts(
            run_dir=run_dir,
            round_number=round_number,
            mutation_raw=mutation.raw_response,
            candidate_spec=normalized_candidate,
            judgement_raw=None,
        )

        if validation_errors:
            stale_count += 1
            record = {
                "kind": "round",
                "round": round_number,
                "accepted": False,
                "track": round_track,
                "base_track": base_track,
                "changed_section": mutation.changed_section,
                "change_summary": mutation.change_summary,
                "score_before": track_score,
                "track_score_before": track_score,
                "track_score_after": track_score,
                "overall_score_before": champion_score,
                "candidate_score": track_score,
                "champion_score": champion_score,
                "constraint_pass": False,
                "violations": validation_errors,
                "summary": "Rejected before judging because the candidate violated structural constraints.",
                "mutation_path": mutation_path,
                "candidate_path": candidate_path,
                "judgement_path": judgement_path,
                "timestamp": int(time.time()),
            }
            append_jsonl(records_path, record)
            rejected_summaries.append(
                f"Round {round_number} | {mutation.changed_section} | {mutation.change_summary} | invalid"
            )
            print(f"  rejected: {'; '.join(validation_errors)}")
            total_rounds_run = round_number
            continue

        try:
            judgement = call_judge(
                client=client,
                model=judge_model,
                reasoning=judge_reasoning,
                spec_text=normalized_candidate,
                rubric_text=rubric_text,
                champion_score=track_score,
                attempts=args.model_attempts,
                temperature=args.judge_temperature,
                search_policy=args.search_policy,
            )
        except SpecLoopError as exc:
            stale_count += 1
            candidate_path, judgement_path, mutation_path = persist_round_artifacts(
                run_dir=run_dir,
                round_number=round_number,
                mutation_raw=mutation.raw_response,
                candidate_spec=normalized_candidate,
                judgement_raw=str(exc),
            )
            record = {
                "kind": "round",
                "round": round_number,
                "accepted": False,
                "track": round_track,
                "base_track": base_track,
                "changed_section": mutation.changed_section,
                "change_summary": mutation.change_summary,
                "score_before": track_score,
                "track_score_before": track_score,
                "track_score_after": track_score,
                "overall_score_before": champion_score,
                "candidate_score": track_score,
                "champion_score": champion_score,
                "constraint_pass": False,
                "violations": [str(exc)],
                "summary": "Rejected because the judge/model call failed after retries.",
                "mutation_path": mutation_path,
                "candidate_path": candidate_path,
                "judgement_path": judgement_path,
                "timestamp": int(time.time()),
            }
            append_jsonl(records_path, record)
            rejected_summaries.append(
                f"Round {round_number} | {mutation.changed_section} | {mutation.change_summary} | judge failed"
            )
            print(f"  rejected: {exc}")
            total_rounds_run = round_number
            continue

        candidate_path, judgement_path, mutation_path = persist_round_artifacts(
            run_dir=run_dir,
            round_number=round_number,
            mutation_raw=mutation.raw_response,
            candidate_spec=normalized_candidate,
            judgement_raw=judgement.raw_response,
        )

        score_before = track_score
        overall_score_before = champion_score
        accepted = judgement.constraint_pass and judgement.total_score > track_score
        signature = candidate_signature(normalized_candidate)
        archive_novelty = novelty_against_archive(signature, search_archive)
        novelty_score = max(judgement.novelty_score, archive_novelty)
        retained_in_archive = accepted
        if search_decision is not None and not accepted:
            retained_in_archive = should_retain_candidate(
                score=judgement.total_score,
                score_before=track_score,
                constraint_pass=judgement.constraint_pass,
                novelty_score=novelty_score,
            )
        commit_sha = None
        overall_track_before = overall_track
        became_overall_champion = False
        if accepted:
            stale_count = 0
            frontier[round_track] = FrontierEntry(
                spec_text=replace_current_champion_score(normalized_candidate, judgement.total_score),
                score=judgement.total_score,
                source_round=round_number,
                changed_section=mutation.changed_section,
                change_summary=mutation.change_summary,
            )
            overall_track = choose_overall_track(frontier)
            champion_score = frontier[overall_track].score
            current_spec = frontier[overall_track].spec_text
            write_frontier(run_dir, frontier, overall_track)
            if overall_track != overall_track_before or champion_score > overall_score_before:
                became_overall_champion = True
                write_text(spec_path, current_spec)
                write_text(run_dir / "winner.md", current_spec)
                if not args.no_git:
                    commit_message = (
                        f"rsaspec: round {round_number:03d} "
                        f"{TRACK_LABELS[round_track]} {format_score(champion_score)}/100 "
                        f"{mutation.changed_section}"
                    )
                    commit_sha = git_commit_path(repo_root, spec_relative_path, commit_message)
            accepted_summaries.append(
                f"Round {round_number} | {round_track} | {mutation.changed_section} | {mutation.change_summary} | "
                f"{format_score(champion_score)}/100"
            )
        else:
            stale_count += 1
            rejected_summaries.append(
                f"Round {round_number} | {round_track} | {mutation.changed_section} | {mutation.change_summary} | "
                f"{format_score(judgement.total_score)}/100"
            )

        if search_decision is not None and retained_in_archive:
            private_signal = normalize_private_judge_signal(
                {
                    "private_feedback": judgement.private_feedback,
                    "socratic_questions": judgement.socratic_questions or [],
                    "uncertainty": judgement.uncertainty,
                    "risk_tags": judgement.risk_tags or [],
                    "novelty_score": judgement.novelty_score,
                }
            )
            candidate_record = CandidateRecord(
                candidate_id=f"round-{round_number:03d}",
                parent_id=search_decision.base_candidate_id,
                round_number=round_number,
                score=judgement.total_score,
                score_before=score_before,
                category_scores=judgement.scores,
                accepted_as_champion=accepted,
                retained_in_archive=True,
                novelty_score=novelty_score,
                search_track=search_decision.track,
                signature=signature,
                private_signal=private_signal,
            )
            search_archive.append(candidate_record_to_dict(candidate_record))
            save_search_archive(search_archive_path, search_archive)

        record = {
            "kind": "round",
            "round": round_number,
            "accepted": accepted,
            "retained_in_archive": retained_in_archive,
            "search_policy": args.search_policy,
            "search_track": search_decision.track if search_decision is not None else round_track,
            "exploration_level": search_decision.exploration_level if search_decision is not None else None,
            "socratic_prompt": search_decision.socratic_prompt if search_decision is not None else None,
            "candidate_signature": signature,
            "novelty_score": novelty_score,
            "track": round_track,
            "base_track": base_track,
            "changed_section": mutation.changed_section,
            "change_summary": mutation.change_summary,
            "score_before": score_before,
            "track_score_before": track_score,
            "track_score_after": frontier[round_track].score if accepted else track_score,
            "overall_score_before": overall_score_before,
            "candidate_score": judgement.total_score,
            "champion_score": champion_score,
            "champion_track": overall_track,
            "became_overall_champion": became_overall_champion,
            "constraint_pass": judgement.constraint_pass,
            "violations": judgement.violations,
            "scores": judgement.scores,
            "category_rationales": judgement.category_rationales,
            "persona_judgements": persona_judgements_from_raw(judgement.raw_response),
            "summary": judgement.summary,
            "private_feedback": judgement.private_feedback,
            "socratic_questions": judgement.socratic_questions or [],
            "uncertainty": judgement.uncertainty,
            "risk_tags": judgement.risk_tags or [],
            "commit": commit_sha,
            "mutation_path": mutation_path,
            "candidate_path": candidate_path,
            "judgement_path": judgement_path,
            "timestamp": int(time.time()),
        }
        append_jsonl(records_path, record)
        prior_persona_feedback = record["persona_judgements"]

        decision_text = "accepted" if accepted else "rejected"
        print(
            f"  {decision_text}: candidate {format_score(judgement.total_score)}/100 | "
            f"track {round_track} {format_score(frontier[round_track].score)}/100 | "
            f"overall {TRACK_LABELS[overall_track]} {format_score(champion_score)}/100"
        )
        total_rounds_run = round_number

    records = load_jsonl(records_path)
    accepted_records = [
        record
        for record in records
        if record.get("kind") == "round" and record.get("accepted")
    ]
    final_report = build_final_report(
        tag=args.tag,
        overall_spec_text=current_spec,
        champion_score=champion_score,
        overall_track=overall_track,
        frontier=frontier,
        rounds_run=total_rounds_run,
        stale_count=stale_count,
        accepted_records=accepted_records,
        search_policy=args.search_policy,
        archived_candidates=len(search_archive),
    )
    write_text(run_dir / "final_report.md", final_report)
    print(f"Done. Final report: {run_dir / 'final_report.md'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SpecLoopError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
