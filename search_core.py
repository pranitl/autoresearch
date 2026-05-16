"""Shared search-controller utilities for spec optimization loops."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CLASSIC_POLICY = "classic"
SOCRATIC_SEARCH_POLICY = "socratic-search"
SEARCH_POLICIES = (CLASSIC_POLICY, SOCRATIC_SEARCH_POLICY)

DEFAULT_SOCRATIC_QUESTIONS = [
    "What buyer-intent assumption has not been tested yet?",
    "What supported angle would widen search space without weakening commercial intent?",
    "What would a strong challenger try if the current champion is overfit to prior wording?",
    "Which part of the decision path can be reframed without changing the underlying offer?",
    "What credible contrast would make this candidate less like the existing asset bank?",
]

SOCRATIC_TRACKS = [
    "conservative",
    "differentiated",
    "synthesis",
    "contrarian",
    "repair",
]

TRACK_DIRECTIVES = {
    "conservative": "Exploit the best current lane with a precise, low-regret refinement.",
    "differentiated": "Explore a meaningfully different supported angle without broadening into weak traffic.",
    "synthesis": "Combine the strongest retained ideas into one promotion-worthy candidate.",
    "contrarian": "Challenge an implicit assumption in the current best path while staying evidence-grounded.",
    "repair": "Fix the largest likely weakness abstractly, without copying the judge's critique.",
}


@dataclass
class PrivateJudgeSignal:
    private_feedback: str
    socratic_questions: list[str]
    uncertainty: float
    risk_tags: list[str]
    novelty_score: float


@dataclass
class SearchDecision:
    base_candidate_id: str
    track: str
    exploration_level: str
    socratic_prompt: str
    hidden_feedback_policy: str
    banned_signatures: list[str]


@dataclass
class CandidateRecord:
    candidate_id: str
    parent_id: str
    round_number: int
    score: float
    score_before: float
    category_scores: dict[str, float]
    accepted_as_champion: bool
    retained_in_archive: bool
    novelty_score: float
    search_track: str
    signature: str
    private_signal: PrivateJudgeSignal


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_private_judge_signal(payload: dict[str, Any]) -> PrivateJudgeSignal:
    questions_input = payload.get("socratic_questions", [])
    if isinstance(questions_input, str):
        questions = [questions_input.strip()] if questions_input.strip() else []
    elif isinstance(questions_input, list):
        questions = [str(item).strip() for item in questions_input if str(item).strip()]
    else:
        questions = []

    risks_input = payload.get("risk_tags", [])
    if isinstance(risks_input, str):
        risk_tags = [risks_input.strip()] if risks_input.strip() else []
    elif isinstance(risks_input, list):
        risk_tags = [str(item).strip() for item in risks_input if str(item).strip()]
    else:
        risk_tags = []

    try:
        uncertainty = float(payload.get("uncertainty", 0.0))
    except (TypeError, ValueError):
        uncertainty = 0.0
    try:
        novelty_score = float(payload.get("novelty_score", 0.0))
    except (TypeError, ValueError):
        novelty_score = 0.0

    return PrivateJudgeSignal(
        private_feedback=str(payload.get("private_feedback", "")).strip(),
        socratic_questions=questions[:3],
        uncertainty=clamp(uncertainty, 0.0, 1.0),
        risk_tags=risk_tags[:8],
        novelty_score=clamp(novelty_score, 0.0, 1.0),
    )


def candidate_signature(text: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    normalized = " ".join(tokens)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def load_search_archive(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def save_search_archive(path: Path, archive: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(archive, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def novelty_against_archive(signature: str, archive: list[dict[str, Any]]) -> float:
    if not archive:
        return 1.0
    if any(item.get("signature") == signature for item in archive):
        return 0.05
    prefix_matches = sum(1 for item in archive if str(item.get("signature", ""))[:4] == signature[:4])
    return round(clamp(1.0 - 0.2 * prefix_matches, 0.2, 1.0), 3)


def choose_socratic_track(round_number: int, stale_count: int) -> str:
    if stale_count >= 4:
        return "contrarian"
    if stale_count >= 2:
        return "differentiated"
    if round_number % 7 == 0:
        return "repair"
    return SOCRATIC_TRACKS[(round_number - 1) % 3]


def exploration_level_for_state(stale_count: int) -> str:
    if stale_count >= 4:
        return "wide"
    if stale_count >= 2:
        return "medium"
    return "focused"


def choose_socratic_question(
    *,
    archive: list[dict[str, Any]],
    round_number: int,
    track: str,
) -> str:
    for item in reversed(archive[-8:]):
        signal = item.get("private_signal")
        if not isinstance(signal, dict):
            continue
        questions = signal.get("socratic_questions")
        if isinstance(questions, list):
            for question in questions:
                question_text = str(question).strip()
                if question_text:
                    return question_text
    default = DEFAULT_SOCRATIC_QUESTIONS[(round_number - 1) % len(DEFAULT_SOCRATIC_QUESTIONS)]
    return f"{default} {TRACK_DIRECTIVES[track]}"


def build_search_decision(
    *,
    policy: str,
    round_number: int,
    stale_count: int,
    archive: list[dict[str, Any]],
    base_candidate_id: str,
) -> SearchDecision | None:
    if policy != SOCRATIC_SEARCH_POLICY:
        return None
    track = choose_socratic_track(round_number, stale_count)
    banned_signatures = [
        str(item["signature"])
        for item in archive[-12:]
        if item.get("signature") and float(item.get("novelty_score", 1.0)) < 0.25
    ][-5:]
    return SearchDecision(
        base_candidate_id=base_candidate_id,
        track=track,
        exploration_level=exploration_level_for_state(stale_count),
        socratic_prompt=choose_socratic_question(
            archive=archive,
            round_number=round_number,
            track=track,
        ),
        hidden_feedback_policy="store judge critique privately; expose only abstract search directives",
        banned_signatures=banned_signatures,
    )


def should_retain_candidate(
    *,
    score: float,
    score_before: float,
    constraint_pass: bool,
    novelty_score: float,
) -> bool:
    if not constraint_pass:
        return False
    if score > score_before:
        return True
    return novelty_score >= 0.75


def candidate_record_to_dict(record: CandidateRecord) -> dict[str, Any]:
    return asdict(record)
