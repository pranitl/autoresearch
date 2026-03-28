"""
Spec optimization loop for page-level CRO experiments.

This keeps the git/research workflow from the native autoresearch repo, but swaps
the CUDA training run for an OpenRouter-driven text optimization loop.

Usage:
    uv run spec_loop.py --spec page_spec.md --tag 20260328-page-spec
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


SECTION_ORDER = [
    "Hero",
    "Owners Section",
    "Services Grid",
    "Featured Page",
    "SEO Content",
    "FAQs",
]

SECTION_MARKERS = {
    "Hero": "1. Hero",
    "Owners Section": "2. Owners Section",
    "Services Grid": "3. Services Grid",
    "Featured Page": "4. Featured Page",
    "SEO Content": "5. SEO Content",
    "FAQs": "6. FAQs",
}

SCORE_CATEGORY_MAXES = {
    "hero_primary_cta_pull": 15.0,
    "service_grid_clickability": 15.0,
    "benefit_emotional_drive": 10.0,
    "trust_local_relevance": 10.0,
    "urgency_next_step_clarity": 10.0,
    "wordpress_compatibility": 10.0,
    "overall_ctr_potential": 30.0,
}

CATEGORY_LABELS = {
    "hero_primary_cta_pull": "Hero & Primary CTA Pull",
    "service_grid_clickability": "Service Grid Clickability",
    "benefit_emotional_drive": "Benefit & Emotional Drive",
    "trust_local_relevance": "Trust & Local Relevance",
    "urgency_next_step_clarity": "Urgency & Next-Step Clarity",
    "wordpress_compatibility": "WordPress Compatibility",
    "overall_ctr_potential": "Overall CTR Potential",
}

FIXED_SERVICES = {"Personal Care", "Companion Care"}
OPTIONAL_SERVICES = {
    "Live in Care",
    "Dementia Care",
    "Veteran Care",
    "Respite Care",
    "Rehab and Recovery Care",
    "Family Care",
    "Travel Companion Services",
    "Disability Care",
}

SCORE_LINE_RE = re.compile(
    r"(?m)^Current champion score:\s*([0-9]+(?:\.[0-9]+)?)/100\s*$"
)
TAG_BLOCK_RE = re.compile(r"(?s)<(?P<tag>[a-z_]+)>\s*(?P<body>.*?)\s*</(?P=tag)>")


class SpecLoopError(RuntimeError):
    """Raised for expected, user-facing loop errors."""


@dataclass
class ParsedSpec:
    header: str
    sections: dict[str, str]


@dataclass
class Mutation:
    changed_section: str
    change_summary: str
    updated_section: str
    raw_response: str


@dataclass
class Judgement:
    constraint_pass: bool
    violations: list[str]
    scores: dict[str, float]
    category_rationales: dict[str, str]
    total_score: float
    summary: str
    raw_response: str


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 120) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        reasoning: dict[str, Any] | None = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        site_url = os.getenv("OPENROUTER_SITE_URL")
        app_name = os.getenv("OPENROUTER_APP_NAME")
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_name:
            headers["X-Title"] = app_name

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if reasoning:
            payload["reasoning"] = reasoning
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:500]
            raise SpecLoopError(f"OpenRouter request failed: {detail}") from exc

        data = response.json()
        try:
            message = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SpecLoopError(
                f"Unexpected OpenRouter response shape: {json.dumps(data)[:500]}"
            ) from exc

        if isinstance(message, str):
            return message
        if isinstance(message, list):
            parts = []
            for item in message:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            joined = "".join(parts).strip()
            if joined:
                return joined
        raise SpecLoopError(f"Unsupported OpenRouter content payload: {message!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenRouter spec optimization loop")
    parser.add_argument("--spec", type=Path, required=True, help="Path to the spec file")
    parser.add_argument(
        "--program",
        type=Path,
        default=Path("spec_program.md"),
        help="Path to the mutator program file",
    )
    parser.add_argument(
        "--rubric",
        type=Path,
        default=Path("scoring_rubric.md"),
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
        default="specsearch",
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
        help="Optional list of section names the mutator may edit during this run",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Disable branch creation and commits",
    )
    return parser.parse_args()


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SpecLoopError(f"Missing required environment variable: {name}")
    return value


def get_reasoning_config(env_name: str) -> dict[str, Any] | None:
    effort = os.getenv(env_name, "").strip().lower()
    if not effort:
        return None
    allowed = {"none", "minimal", "low", "medium", "high", "xhigh"}
    if effort not in allowed:
        raise SpecLoopError(
            f"{env_name} must be one of {sorted(allowed)}; got {effort!r}."
        )
    return {"effort": effort}


def load_text_file(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SpecLoopError(f"{label} not found: {path}") from exc


def load_spec(path: Path) -> str:
    return load_text_file(path, "Spec file")


def load_program(path: Path) -> str:
    return load_text_file(path, "Program file")


def parse_score_from_spec(text: str) -> float | None:
    match = SCORE_LINE_RE.search(text)
    if not match:
        return None
    return float(match.group(1))


def format_score(score: float) -> str:
    rounded = round(score, 1)
    if math.isclose(rounded, round(rounded), abs_tol=1e-9):
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def replace_current_champion_score(text: str, score: float) -> str:
    if not SCORE_LINE_RE.search(text):
        raise SpecLoopError("Spec is missing the 'Current champion score' line.")
    return SCORE_LINE_RE.sub(
        f"Current champion score: {format_score(score)}/100", text, count=1
    )


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


def section_marker_pattern(section_name: str) -> str:
    marker = SECTION_MARKERS[section_name]
    return rf"(?m)^{re.escape(marker)}(?:\b.*)?$"


def normalize_header_for_compare(header: str) -> str:
    return SCORE_LINE_RE.sub("Current champion score: __SCORE__/100", header)


def find_changed_sections(current_spec: str, candidate_spec: str) -> list[str]:
    current = parse_spec(current_spec)
    candidate = parse_spec(candidate_spec)
    changed = []
    for section_name in SECTION_ORDER:
        if current.sections[section_name] != candidate.sections[section_name]:
            changed.append(section_name)
    return changed


def splice_updated_section(
    current_spec: str,
    section_name: str,
    updated_section: str,
) -> str:
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


def validate_hero_section(section_text: str) -> list[str]:
    errors = []
    match = re.search(r"(?m)^\s*(?:Headline|Hero Keyword):\s*(.+?)\s*$", section_text)
    if not match:
        return ["Hero section is missing a 'Headline:' or 'Hero Keyword:' line."]
    headline = match.group(1).strip()
    if len(headline) > 60:
        errors.append(f"Hero headline exceeds 60 characters ({len(headline)}).")
    return errors


def parse_service_name(line: str) -> tuple[str, bool]:
    label = line.strip()
    is_fixed = label.endswith("(fixed)")
    if is_fixed:
        label = label[: -len("(fixed)")].rstrip()
    return label, is_fixed


def extract_labeled_bullets(section_text: str, label: str) -> list[str]:
    pattern = rf"(?m)^\s*\*\*?{re.escape(label)}\*\*?:\s*\n(?P<body>(?:\s*-\s+[^\n]+\n)+)"
    match = re.search(pattern, section_text)
    if not match:
        pattern = rf"(?m)^\s*{re.escape(label)}:\s*\n(?P<body>(?:\s*-\s+[^\n]+\n)+)"
        match = re.search(pattern, section_text)
    if not match:
        return []
    return re.findall(r"(?m)^\s*-\s+(.+?)\s*$", match.group("body"))


def validate_services_section(section_text: str) -> list[str]:
    errors = []
    service_lines = extract_labeled_bullets(section_text, "Services to Show")
    if len(service_lines) != 6:
        errors.append(f"Services Grid must list exactly 6 services; found {len(service_lines)}.")
        return errors

    seen_names = []
    for raw_line in service_lines:
        service_name, is_fixed = parse_service_name(raw_line)
        seen_names.append(service_name)
        if service_name in FIXED_SERVICES and not is_fixed:
            errors.append(f"{service_name} must keep its '(fixed)' marker.")
        if service_name not in FIXED_SERVICES and is_fixed:
            errors.append(f"{service_name} cannot be marked as fixed.")
        if service_name not in FIXED_SERVICES | OPTIONAL_SERVICES:
            errors.append(f"Unsupported service in grid: {service_name}.")

    if len(set(seen_names)) != 6:
        errors.append("Services Grid cannot include duplicate services.")
    for required_name in sorted(FIXED_SERVICES):
        if required_name not in seen_names:
            errors.append(f"Services Grid must include {required_name}.")
    return errors


def validate_featured_page_section(section_text: str) -> list[str]:
    errors = []
    match = re.search(r"(?m)^\s*(?:Selected page|Link text / section title):\s*(.+?)\s*$", section_text)
    blank_match = re.search(r"(?m)^\s*(?:Selected page|Link text / section title):\s*$", section_text)
    if not match and not blank_match:
        return ["Featured Page section is missing the selected-page line."]

    selected_value = match.group(1).strip() if match else ""
    available_options = extract_labeled_bullets(section_text, "Available options")
    if selected_value and available_options and selected_value not in available_options:
        errors.append(
            "Featured Page selected value is invalid; it must be one of the listed options "
            f"({', '.join(available_options)}), not {selected_value!r}."
        )
    if "Keep the selected page set to About us for this experiment." in section_text and selected_value != "About us":
        errors.append("Featured Page selected value must remain 'About us' for this experiment.")

    content_match = re.search(
        r"(?ms)^\s*Custom content:\s*\n(?P<body>.*?)(?=^\s*Available options:)",
        section_text,
    )
    if content_match:
        raw_content = content_match.group("body").strip()
        normalized_content = re.sub(r"\s+", " ", raw_content).strip()
        if re.search(r"\[[^\]]+\]\([^)]+\)|[*_`#>|]", raw_content):
            errors.append("Featured Page custom content must be plain text only.")
        if normalized_content and len(normalized_content) > 200:
            errors.append(
                f"Featured Page custom content exceeds 200 characters ({len(normalized_content)})."
            )

    return errors


def validate_faq_section(section_text: str) -> list[str]:
    errors = []
    question_lines = re.findall(r"(?m)^ {3}([1-5])\.\s+(.+?)\s*$", section_text)
    if len(question_lines) != 5 or [int(item[0]) for item in question_lines] != [1, 2, 3, 4, 5]:
        errors.append("FAQs must include exactly 5 top-level question lines numbered 1-5.")
    answer_lines = re.findall(r"(?m)^ {6,}[1-9]\.\s+(.+?)\s*$", section_text)
    if len(answer_lines) < 5:
        errors.append("Each FAQ needs an associated answer line.")
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
    if declared_section not in SECTION_ORDER:
        errors.append(f"Changed section must be one of {SECTION_ORDER}; got {declared_section!r}.")
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

    errors.extend(validate_hero_section(candidate.sections["Hero"]))
    errors.extend(validate_services_section(candidate.sections["Services Grid"]))
    errors.extend(validate_featured_page_section(candidate.sections["Featured Page"]))
    errors.extend(validate_faq_section(candidate.sections["FAQs"]))
    return normalized_candidate, errors


def extract_tagged_block(raw_text: str, tag_name: str) -> str:
    for match in TAG_BLOCK_RE.finditer(raw_text):
        if match.group("tag") == tag_name:
            return match.group("body").strip()
    raise SpecLoopError(f"Response is missing <{tag_name}>...</{tag_name}>.")


def parse_mutation(raw_text: str) -> Mutation:
    metadata_text = extract_tagged_block(raw_text, "mutation")
    updated_section = extract_tagged_block(raw_text, "updated_section")
    try:
        metadata = json.loads(metadata_text)
    except json.JSONDecodeError as exc:
        raise SpecLoopError(f"Invalid JSON inside <mutation>: {exc}") from exc

    changed_section = metadata.get("changed_section")
    change_summary = metadata.get("change_summary")
    if not isinstance(changed_section, str) or not changed_section.strip():
        raise SpecLoopError("Mutation metadata is missing 'changed_section'.")
    if not isinstance(change_summary, str) or not change_summary.strip():
        raise SpecLoopError("Mutation metadata is missing 'change_summary'.")
    if not updated_section.strip():
        raise SpecLoopError("Mutation is missing the updated section.")
    return Mutation(
        changed_section=changed_section.strip(),
        change_summary=change_summary.strip(),
        updated_section=updated_section.strip() + "\n",
        raw_response=raw_text,
    )


def extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        raise SpecLoopError("Model returned an empty response.")
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced_match:
        fenced_body = fenced_match.group(1).strip()
        try:
            json.loads(fenced_body)
            return fenced_body
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise SpecLoopError("Could not locate a valid JSON object in the model response.")


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
    return Judgement(
        constraint_pass=bool(payload["constraint_pass"]),
        violations=[str(item) for item in violations],
        scores=scores,
        category_rationales=rationales,
        total_score=round(total_score, 2),
        summary=str(payload.get("summary", "")).strip(),
        raw_response=raw_text,
    )


def build_mutator_prompt(
    *,
    program_text: str,
    target_file_name: str,
    spec_text: str,
    champion_score: float,
    round_number: int,
    accepted_summaries: list[str],
    recent_rejections: list[str],
    allowed_sections: list[str] | None = None,
    retry_feedback: str | None = None,
) -> list[dict[str, str]]:
    accepted_block = "\n".join(f"- {item}" for item in accepted_summaries[-8:]) or "- None yet"
    rejected_block = "\n".join(f"- {item}" for item in recent_rejections[-5:]) or "- None yet"
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
        You may only edit the target spec file supplied by the runner.
        Return exactly this format:
        <mutation>
        {"changed_section":"Hero","change_summary":"One sentence summary."}
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

        Goal: maximize CTR on Request Pricing, phone clicks, service links, and Contact Our Team.
        Current champion score: {format_score(champion_score)}/100
        Round: {round_number}

        Accepted improvements so far:
        {accepted_block}

        Recent rejected ideas:
        {rejected_block}
        {allowed_block}
        {retry_block}
        Runner requirements:
        - Keep the "Current champion score" line unchanged. The runner will update it if you win.
        - Return only the single updated section, including its section marker.
        - Do not reprint the whole file.

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
    retry_feedback: str | None = None,
) -> list[dict[str, str]]:
    retry_block = f"\nYour previous response failed parsing for this reason:\n{retry_feedback}\n" if retry_feedback else ""
    system_prompt = textwrap.dedent(
        """
        You are a strict CRO judge scoring a landing-page optimization spec.
        Score the candidate independently against the rubric below.
        Return JSON only.

        Required JSON shape:
        {
          "constraint_pass": true,
          "violations": ["..."],
          "scores": {
            "hero_primary_cta_pull": 0,
            "service_grid_clickability": 0,
            "benefit_emotional_drive": 0,
            "trust_local_relevance": 0,
            "urgency_next_step_clarity": 0,
            "wordpress_compatibility": 0,
            "overall_ctr_potential": 0
          },
          "category_rationales": {
            "hero_primary_cta_pull": "brief rationale",
            "service_grid_clickability": "brief rationale",
            "benefit_emotional_drive": "brief rationale",
            "trust_local_relevance": "brief rationale",
            "urgency_next_step_clarity": "brief rationale",
            "wordpress_compatibility": "brief rationale",
            "overall_ctr_potential": "brief rationale"
          },
          "total_score": 0,
          "summary": "brief summary"
        }
        """
    ).strip()
    user_prompt = textwrap.dedent(
        f"""
        Candidate spec to score:
        <spec>
        {spec_text}
        </spec>

        Locked scoring rubric:
        <rubric>
        {rubric_text}
        </rubric>

        Current champion score threshold: {format_score(champion_score)}/100
        {retry_block}
        Use these rubric maxima:
        - hero_primary_cta_pull: 15
        - service_grid_clickability: 15
        - benefit_emotional_drive: 10
        - trust_local_relevance: 10
        - urgency_next_step_clarity: 10
        - wordpress_compatibility: 10
        - overall_ctr_potential: 30

        Keep rationales short and concrete.
        """
    ).strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def run_subprocess(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise SpecLoopError(
            f"Command failed ({' '.join(args)}):\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


def ensure_git_branch(repo_root: Path, branch_name: str) -> None:
    current_branch = run_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root
    ).stdout.strip()
    if current_branch == branch_name:
        return

    exists = run_subprocess(
        ["git", "rev-parse", "--verify", branch_name],
        repo_root,
        check=False,
    )
    if exists.returncode == 0:
        run_subprocess(["git", "checkout", branch_name], repo_root)
    else:
        run_subprocess(["git", "checkout", "-b", branch_name], repo_root)


def git_file_status(repo_root: Path, relative_path: str) -> str:
    return run_subprocess(
        ["git", "status", "--porcelain", "--", relative_path], repo_root
    ).stdout.strip()


def git_head_sha(repo_root: Path) -> str:
    return run_subprocess(["git", "rev-parse", "--short", "HEAD"], repo_root).stdout.strip()


def git_commit_path(repo_root: Path, relative_path: str, message: str) -> str | None:
    status = git_file_status(repo_root, relative_path)
    if not status:
        return None
    run_subprocess(["git", "add", "--", relative_path], repo_root)
    run_subprocess(["git", "commit", "-m", message, "--", relative_path], repo_root)
    return git_head_sha(repo_root)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_resume_state(records: list[dict[str, Any]]) -> tuple[int, float, int]:
    if not records:
        return 1, 0.0, 0
    round_records = [record for record in records if record.get("kind") == "round"]
    champion_score = float(records[-1]["champion_score"])
    if not round_records:
        return 1, champion_score, 0
    last_round = max(int(record["round"]) for record in round_records)
    stale_count = 0
    for record in reversed(round_records):
        if record.get("accepted"):
            break
        stale_count += 1
    return last_round + 1, champion_score, stale_count


def recent_history(records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    accepted = []
    rejected = []
    for record in records:
        if record.get("kind") != "round":
            continue
        summary = record.get("change_summary", "").strip()
        section = record.get("changed_section", "")
        total = record.get("candidate_score", record.get("champion_score"))
        rendered = f"Round {record['round']} | {section} | {summary} | {format_score(float(total))}/100"
        if record.get("accepted"):
            accepted.append(rendered)
        else:
            rejected.append(rendered)
    return accepted, rejected


def get_repo_root(spec_path: Path) -> Path:
    return spec_path.resolve().parent


def ensure_git_repo(repo_root: Path) -> None:
    completed = run_subprocess(
        ["git", "rev-parse", "--show-toplevel"],
        repo_root,
        check=False,
    )
    if completed.returncode != 0:
        raise SpecLoopError("Git integration is enabled, but this directory is not a git repo.")


def persist_round_artifacts(
    *,
    run_dir: Path,
    round_number: int,
    mutation_raw: str,
    candidate_spec: str | None,
    judgement_raw: str | None,
) -> tuple[str | None, str | None, str]:
    raw_dir = run_dir / "raw"
    candidate_dir = run_dir / "candidates"
    judgement_dir = run_dir / "judgements"
    mutation_path = raw_dir / f"round-{round_number:03d}-mutation.txt"
    write_text(mutation_path, mutation_raw)

    candidate_path: str | None = None
    if candidate_spec is not None:
        candidate_file = candidate_dir / f"round-{round_number:03d}.md"
        write_text(candidate_file, candidate_spec)
        candidate_path = str(candidate_file.relative_to(run_dir))

    judgement_path: str | None = None
    if judgement_raw is not None:
        judgement_file = judgement_dir / f"round-{round_number:03d}.json"
        write_text(judgement_file, judgement_raw)
        judgement_path = str(judgement_file.relative_to(run_dir))
    return candidate_path, judgement_path, str(mutation_path.relative_to(run_dir))


def call_mutator(
    *,
    client: OpenRouterClient,
    model: str,
    reasoning: dict[str, Any] | None,
    program_text: str,
    target_file_name: str,
    spec_text: str,
    champion_score: float,
    round_number: int,
    accepted_summaries: list[str],
    recent_rejections: list[str],
    allowed_sections: list[str] | None,
    attempts: int,
    temperature: float,
) -> Mutation:
    retry_feedback: str | None = None
    for _ in range(attempts):
        messages = build_mutator_prompt(
            program_text=program_text,
            target_file_name=target_file_name,
            spec_text=spec_text,
            champion_score=champion_score,
            round_number=round_number,
            accepted_summaries=accepted_summaries,
            recent_rejections=recent_rejections,
            allowed_sections=allowed_sections,
            retry_feedback=retry_feedback,
        )
        raw_response = client.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            reasoning=reasoning,
        )
        try:
            return parse_mutation(raw_response)
        except SpecLoopError as exc:
            retry_feedback = str(exc)
            last_response = raw_response
    raise SpecLoopError(
        f"Mutator failed after {attempts} attempts. Last error: {retry_feedback}\n"
        f"Last response:\n{last_response}"
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
) -> Judgement:
    retry_feedback: str | None = None
    for _ in range(attempts):
        messages = build_judge_prompt(
            spec_text=spec_text,
            rubric_text=rubric_text,
            champion_score=champion_score,
            retry_feedback=retry_feedback,
        )
        raw_response = client.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            reasoning=reasoning,
        )
        try:
            return parse_judgement(raw_response)
        except SpecLoopError as exc:
            retry_feedback = str(exc)
            last_response = raw_response
    raise SpecLoopError(
        f"Judge failed after {attempts} attempts. Last error: {retry_feedback}\n"
        f"Last response:\n{last_response}"
    )


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
) -> tuple[str, float, list[dict[str, Any]], str | None]:
    records = load_jsonl(records_path)
    if records:
        champion_score = float(records[-1]["champion_score"])
        return current_spec, champion_score, records, records[-1].get("commit")

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
        commit_message = f"specsearch: baseline {tag} ({format_score(baseline_score)}/100)"
        commit_sha = git_commit_path(repo_root, spec_relative_path, commit_message) or git_head_sha(repo_root)

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
        "candidate_score": baseline_score,
        "champion_score": baseline_score,
        "change_summary": "baseline",
        "changed_section": "baseline",
        "summary": baseline_judgement.summary,
        "commit": commit_sha,
        "timestamp": int(time.time()),
    }
    append_jsonl(records_path, baseline_record)
    return normalized_spec, baseline_score, [baseline_record], commit_sha


def build_final_report(
    *,
    tag: str,
    spec_text: str,
    champion_score: float,
    rounds_run: int,
    stale_count: int,
    accepted_records: list[dict[str, Any]],
) -> str:
    top_changes = sorted(
        accepted_records,
        key=lambda record: float(record["candidate_score"]) - float(record["score_before"]),
        reverse=True,
    )[:3]
    lines = [
        f"# Specsearch Report: {tag}",
        "",
        f"Final champion score: {format_score(champion_score)}/100",
        f"Rounds completed: {rounds_run}",
        f"Accepted improvements: {len(accepted_records)}",
        f"Ending stale count: {stale_count}",
        "",
        "## Top 3 CTR-driving changes",
    ]
    if top_changes:
        for index, record in enumerate(top_changes, start=1):
            delta = float(record["candidate_score"]) - float(record["score_before"])
            lines.append(
                f"{index}. {record['changed_section']}: {record['change_summary']} (+{delta:.1f})"
            )
    else:
        lines.append("1. No accepted improvements yet.")

    lines.extend(
        [
            "",
            "## Winning version",
            "```md",
            spec_text.rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    allowed_sections = None
    if args.allowed_sections:
        invalid_sections = [item for item in args.allowed_sections if item not in SECTION_ORDER]
        if invalid_sections:
            raise SpecLoopError(
                f"--allowed-sections contains invalid section names: {invalid_sections}. "
                f"Valid sections: {SECTION_ORDER}"
            )
        allowed_sections = list(args.allowed_sections)
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
    current_spec, champion_score, records, _baseline_commit = baseline_if_needed(
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

    start_round, champion_score, stale_count = load_resume_state(load_jsonl(records_path))
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
    accepted_summaries, rejected_summaries = recent_history(records)

    for round_number in range(start_round, args.rounds + 1):
        if stale_count >= args.stale_limit:
            print(f"Stopping early after {stale_count} consecutive rejected rounds.")
            break

        print(
            f"Round {round_number}/{args.rounds} | champion {format_score(champion_score)}/100 | "
            f"stale {stale_count}/{args.stale_limit}"
        )
        mutation = call_mutator(
            client=client,
            model=mutator_model,
            reasoning=mutator_reasoning,
            program_text=program_text,
            target_file_name=spec_path.name,
            spec_text=current_spec,
            champion_score=champion_score,
            round_number=round_number,
            accepted_summaries=accepted_summaries,
            recent_rejections=rejected_summaries,
            allowed_sections=allowed_sections,
            attempts=args.model_attempts,
            temperature=args.mutator_temperature,
        )

        try:
            candidate_spec = splice_updated_section(
                current_spec=current_spec,
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
                "changed_section": mutation.changed_section,
                "change_summary": mutation.change_summary,
                "score_before": champion_score,
                "candidate_score": champion_score,
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
            current_spec=current_spec,
            candidate_spec=candidate_spec,
            declared_section=mutation.changed_section,
            current_score=champion_score,
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
                "changed_section": mutation.changed_section,
                "change_summary": mutation.change_summary,
                "score_before": champion_score,
                "candidate_score": champion_score,
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

        judgement = call_judge(
            client=client,
            model=judge_model,
            reasoning=judge_reasoning,
            spec_text=normalized_candidate,
            rubric_text=rubric_text,
            champion_score=champion_score,
            attempts=args.model_attempts,
            temperature=args.judge_temperature,
        )
        candidate_path, judgement_path, mutation_path = persist_round_artifacts(
            run_dir=run_dir,
            round_number=round_number,
            mutation_raw=mutation.raw_response,
            candidate_spec=normalized_candidate,
            judgement_raw=judgement.raw_response,
        )

        score_before = champion_score
        accepted = judgement.constraint_pass and judgement.total_score > champion_score
        commit_sha = None
        updated_spec = current_spec
        if accepted:
            stale_count = 0
            champion_score = judgement.total_score
            updated_spec = replace_current_champion_score(normalized_candidate, champion_score)
            write_text(spec_path, updated_spec)
            write_text(run_dir / "winner.md", updated_spec)
            if not args.no_git:
                commit_message = (
                    f"specsearch: round {round_number:03d} "
                    f"{format_score(champion_score)}/100 {mutation.changed_section}"
                )
                commit_sha = git_commit_path(repo_root, spec_relative_path, commit_message)
            current_spec = updated_spec
            accepted_summaries.append(
                f"Round {round_number} | {mutation.changed_section} | {mutation.change_summary} | "
                f"{format_score(champion_score)}/100"
            )
        else:
            stale_count += 1
            rejected_summaries.append(
                f"Round {round_number} | {mutation.changed_section} | {mutation.change_summary} | "
                f"{format_score(judgement.total_score)}/100"
            )

        record = {
            "kind": "round",
            "round": round_number,
            "accepted": accepted,
            "changed_section": mutation.changed_section,
            "change_summary": mutation.change_summary,
            "score_before": score_before,
            "candidate_score": judgement.total_score,
            "champion_score": champion_score,
            "constraint_pass": judgement.constraint_pass,
            "violations": judgement.violations,
            "scores": judgement.scores,
            "category_rationales": judgement.category_rationales,
            "summary": judgement.summary,
            "commit": commit_sha,
            "mutation_path": mutation_path,
            "candidate_path": candidate_path,
            "judgement_path": judgement_path,
            "timestamp": int(time.time()),
        }
        append_jsonl(records_path, record)

        decision_text = "accepted" if accepted else "rejected"
        print(
            f"  {decision_text}: candidate {format_score(judgement.total_score)}/100 | "
            f"champion {format_score(champion_score)}/100"
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
        spec_text=current_spec,
        champion_score=champion_score,
        rounds_run=total_rounds_run,
        stale_count=stale_count,
        accepted_records=accepted_records,
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
