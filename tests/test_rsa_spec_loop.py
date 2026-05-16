import json
import re
import unittest
from pathlib import Path

import rsa_spec_loop
from search_core import (
    SOCRATIC_SEARCH_POLICY,
    SearchDecision,
    should_retain_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
RSA_SPEC = (ROOT / "rsa_audit_spec.md").read_text(encoding="utf-8")
RSA_PROGRAM = (ROOT / "rsa_spec_program.md").read_text(encoding="utf-8")
RSA_RUBRIC = (ROOT / "rsa_scoring_rubric.md").read_text(encoding="utf-8")


class RsaSpecLoopTests(unittest.TestCase):
    def update_editable_block(self, section_name: str, old: str, new: str) -> str:
        parsed = rsa_spec_loop.parse_spec(RSA_SPEC)
        section = parsed.sections[section_name]
        prefix, body = rsa_spec_loop.split_editable_block(section)
        updated_body = body.replace(old, new, 1)
        return rsa_spec_loop.splice_updated_section(
            RSA_SPEC,
            section_name,
            prefix + updated_body,
        )

    def test_validate_candidate_accepts_single_active_block_change(self) -> None:
        candidate = self.update_editable_block(
            "Private Home Care Near Me",
            "Home Care Services Near You",
            "Trusted Home Care Nearby",
        )
        normalized, errors = rsa_spec_loop.validate_candidate_spec(
            current_spec=RSA_SPEC,
            candidate_spec=candidate,
            declared_section="Private Home Care Near Me",
            current_score=71.0,
        )
        self.assertFalse(errors)
        self.assertIn("Current champion score: 71/100", normalized)

    def test_validate_candidate_rejects_locked_evidence_change(self) -> None:
        candidate = RSA_SPEC.replace(
            "Keyword reality: 6 enabled / 14 paused / 4 enabled keywords with impressions in the last 30d",
            "Keyword reality: 999 enabled / 14 paused / 4 enabled keywords with impressions in the last 30d",
            1,
        )
        _, errors = rsa_spec_loop.validate_candidate_spec(
            current_spec=RSA_SPEC,
            candidate_spec=candidate,
            declared_section="Core Non-Medical Home Care",
            current_score=71.0,
        )
        self.assertTrue(any("Locked evidence changed inside Core Non-Medical Home Care" in item for item in errors))

    def test_validate_candidate_rejects_multiple_active_section_changes(self) -> None:
        candidate = RSA_SPEC.replace(
            "Home Care Services Near You",
            "Trusted Home Care Nearby",
            1,
        ).replace(
            "Adult Home Care Services",
            "Senior Support That Fits",
            1,
        )
        _, errors = rsa_spec_loop.validate_candidate_spec(
            current_spec=RSA_SPEC,
            candidate_spec=candidate,
            declared_section="Private Home Care Near Me",
            current_score=71.0,
        )
        self.assertTrue(any("Exactly one editable section may change" in item for item in errors))

    def test_validate_candidate_rejects_wrong_fixed_url(self) -> None:
        candidate = RSA_SPEC.replace(
            "Fixed recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`",
            "Fixed recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/`",
            1,
        )
        _, errors = rsa_spec_loop.validate_candidate_spec(
            current_spec=RSA_SPEC,
            candidate_spec=candidate,
            declared_section="Core Non-Medical Home Care",
            current_score=71.0,
        )
        self.assertTrue(any("Fixed recommended URL for Core Non-Medical Home Care must remain" in item for item in errors))

    def test_validate_candidate_rejects_phone_numbers(self) -> None:
        candidate = self.update_editable_block(
            "Core Non-Medical Home Care",
            "Free Consultation Today",
            "Call 781-874-9901",
        )
        _, errors = rsa_spec_loop.validate_candidate_spec(
            current_spec=RSA_SPEC,
            candidate_spec=candidate,
            declared_section="Core Non-Medical Home Care",
            current_score=71.0,
        )
        self.assertTrue(any("phone numbers" in item.lower() for item in errors))

    def test_validate_candidate_rejects_bad_theme_coverage(self) -> None:
        replacement_headlines = "\n".join(
            f"- Home Care Nearby {index:02d}" for index in range(1, 16)
        )
        candidate = re.sub(
            r"(?ms)^Headlines:\n(?:-\s+[^\n]+\n){15}",
            "Headlines:\n" + replacement_headlines + "\n",
            RSA_SPEC,
            count=1,
        )
        _, errors = rsa_spec_loop.validate_candidate_spec(
            current_spec=RSA_SPEC,
            candidate_spec=candidate,
            declared_section="Core Non-Medical Home Care",
            current_score=71.0,
        )
        self.assertTrue(any("at least 5 distinct themes" in item for item in errors))

    def test_splice_updated_section_only_changes_target_section(self) -> None:
        updated = self.update_editable_block(
            "Private Home Care Near Me",
            "Home Care Services Near You",
            "Trusted Home Care Nearby",
        )
        self.assertEqual(
            rsa_spec_loop.find_changed_sections(RSA_SPEC, updated),
            ["Private Home Care Near Me"],
        )

    def test_build_mutator_prompt_uses_program_file(self) -> None:
        frontier = rsa_spec_loop.default_frontier(RSA_SPEC, 71.0)
        messages = rsa_spec_loop.build_mutator_prompt(
            program_text=RSA_PROGRAM,
            target_file_name="rsa_audit_spec.md",
            spec_text=RSA_SPEC,
            champion_score=71.0,
            track_name="conservative",
            track_score=71.0,
            base_track_name="conservative",
            frontier_snapshot=rsa_spec_loop.render_frontier_snapshot(frontier, "conservative"),
            round_number=1,
            accepted_summaries=[],
            recent_rejections=[],
            allowed_sections=rsa_spec_loop.ACTIVE_SECTIONS,
        )
        self.assertIn("<program>", messages[1]["content"])
        self.assertIn("You are running an autonomous RSA hypothesis-refinement loop", messages[1]["content"])
        self.assertIn("Target file to edit: rsa_audit_spec.md", messages[1]["content"])
        self.assertIn("Frontier track for this round: Conservative", messages[1]["content"])
        self.assertIn("Prior-round persona judge feedback:", messages[1]["content"])

    def test_build_mutator_prompt_includes_prior_persona_feedback(self) -> None:
        frontier = rsa_spec_loop.default_frontier(RSA_SPEC, 71.0)
        messages = rsa_spec_loop.build_mutator_prompt(
            program_text=RSA_PROGRAM,
            target_file_name="rsa_audit_spec.md",
            spec_text=RSA_SPEC,
            champion_score=71.0,
            track_name="conservative",
            track_score=71.0,
            base_track_name="conservative",
            frontier_snapshot=rsa_spec_loop.render_frontier_snapshot(frontier, "conservative"),
            round_number=2,
            accepted_summaries=[],
            recent_rejections=[],
            prior_persona_feedback=[
                {
                    "persona_name": "The Overwhelmed Adult Child",
                    "total_score": 82,
                    "feedback": "Make the immediate crisis relief clearer.",
                },
                {
                    "persona_name": "The Exhausted Spouse Caregiver",
                    "total_score": 76,
                    "feedback": "Show flexible respite without long commitments.",
                },
            ],
            allowed_sections=rsa_spec_loop.ACTIVE_SECTIONS,
        )
        prompt = messages[1]["content"]
        self.assertIn("The Overwhelmed Adult Child (82/100): Make the immediate crisis relief clearer.", prompt)
        self.assertIn("The Exhausted Spouse Caregiver (76/100): Show flexible respite without long commitments.", prompt)

    def test_pick_frontier_track_rotates_three_lanes(self) -> None:
        self.assertEqual(rsa_spec_loop.pick_frontier_track(1), "conservative")
        self.assertEqual(rsa_spec_loop.pick_frontier_track(2), "differentiated")
        self.assertEqual(rsa_spec_loop.pick_frontier_track(3), "synthesis")
        self.assertEqual(rsa_spec_loop.pick_frontier_track(4), "conservative")

    def test_synthesis_base_track_uses_best_available_frontier(self) -> None:
        frontier = rsa_spec_loop.default_frontier(RSA_SPEC, 71.0)
        frontier["differentiated"] = rsa_spec_loop.FrontierEntry(
            spec_text=RSA_SPEC,
            score=78.0,
            source_round=4,
            changed_section="Private Home Care Near Me",
            change_summary="Sharper private-pay near-me angle.",
        )
        self.assertEqual(
            rsa_spec_loop.choose_base_track("synthesis", frontier, "differentiated"),
            "differentiated",
        )

    def test_build_judge_prompt_uses_external_rubric(self) -> None:
        messages = rsa_spec_loop.build_judge_prompt(
            spec_text=RSA_SPEC,
            rubric_text=RSA_RUBRIC,
            champion_score=44.0,
        )
        self.assertIn("<rubric>", messages[1]["content"])
        self.assertIn("Locked RSA Scoring Rubric", messages[1]["content"])

    def test_socratic_mutator_prompt_hides_private_feedback(self) -> None:
        frontier = rsa_spec_loop.default_frontier(RSA_SPEC, 71.0)
        private_feedback = "D1 is too narrow and should mention pricing."
        decision = SearchDecision(
            base_candidate_id="conservative:round-0",
            track="contrarian",
            exploration_level="wide",
            socratic_prompt="What buyer-intent assumption has not been tested yet?",
            hidden_feedback_policy="store judge critique privately",
            banned_signatures=["abc123"],
        )
        messages = rsa_spec_loop.build_mutator_prompt(
            program_text=RSA_PROGRAM,
            target_file_name="rsa_audit_spec.md",
            spec_text=RSA_SPEC,
            champion_score=71.0,
            track_name="conservative",
            track_score=71.0,
            base_track_name="conservative",
            frontier_snapshot=rsa_spec_loop.render_frontier_snapshot(frontier, "conservative"),
            round_number=5,
            accepted_summaries=[],
            recent_rejections=[private_feedback],
            allowed_sections=rsa_spec_loop.ACTIVE_SECTIONS,
            search_decision=decision,
        )
        prompt = messages[1]["content"]
        self.assertIn("Socratic search directive", prompt)
        self.assertIn("What buyer-intent assumption has not been tested yet?", prompt)
        self.assertIn("Hidden in this policy", prompt)
        self.assertNotIn(private_feedback, prompt)

    def test_socratic_judge_prompt_requests_private_controller_metadata(self) -> None:
        messages = rsa_spec_loop.build_judge_prompt(
            spec_text=RSA_SPEC,
            rubric_text=RSA_RUBRIC,
            champion_score=71.0,
            search_policy=SOCRATIC_SEARCH_POLICY,
        )
        combined = "\n".join(message["content"] for message in messages)
        self.assertIn('"private_feedback"', combined)
        self.assertIn('"socratic_questions"', combined)
        self.assertIn("next draft should use", combined)

    def test_parse_judgement_keeps_private_metadata(self) -> None:
        payload = {
            "constraint_pass": True,
            "violations": [],
            "scores": {
                "query_message_fit": 18,
                "ctr_lift_vs_live_comparators": 17,
                "click_quality_protection": 14,
                "trust_private_pay_specificity": 14,
                "landing_page_fit": 9,
                "rsa_diversity_strength": 8,
                "policy_brand_safety": 10,
            },
            "category_rationales": {
                "query_message_fit": "ok",
                "ctr_lift_vs_live_comparators": "ok",
                "click_quality_protection": "ok",
                "trust_private_pay_specificity": "ok",
                "landing_page_fit": "ok",
                "rsa_diversity_strength": "ok",
                "policy_brand_safety": "ok",
            },
            "private_feedback": "Useful private diagnosis.",
            "socratic_questions": ["What alternate buyer assumption should be tested?"],
            "uncertainty": 0.35,
            "risk_tags": ["overfit"],
            "novelty_score": 0.8,
            "total_score": 90,
            "summary": "ok",
        }
        judgement = rsa_spec_loop.parse_judgement(json.dumps(payload))
        self.assertEqual(judgement.private_feedback, "Useful private diagnosis.")
        self.assertEqual(judgement.socratic_questions, ["What alternate buyer assumption should be tested?"])
        self.assertEqual(judgement.risk_tags, ["overfit"])
        self.assertEqual(judgement.novelty_score, 0.8)

    def test_aggregate_persona_judgements_equal_weights_scores(self) -> None:
        def make_judgement(total: float, feedback: str) -> rsa_spec_loop.Judgement:
            scores = {
                "query_message_fit": total * 0.20,
                "ctr_lift_vs_live_comparators": total * 0.20,
                "click_quality_protection": total * 0.15,
                "trust_private_pay_specificity": total * 0.15,
                "landing_page_fit": total * 0.10,
                "rsa_diversity_strength": total * 0.10,
                "policy_brand_safety": total * 0.10,
            }
            return rsa_spec_loop.Judgement(
                constraint_pass=True,
                violations=[],
                scores=scores,
                category_rationales={key: "ok" for key in scores},
                total_score=total,
                summary=f"{total}",
                raw_response="{}",
                private_feedback=feedback,
            )

        persona_judgements = [
            rsa_spec_loop.PersonaJudgement(
                persona=rsa_spec_loop.HOME_CARE_PERSONAS[0],
                judgement=make_judgement(80.0, "Adult-child feedback."),
            ),
            rsa_spec_loop.PersonaJudgement(
                persona=rsa_spec_loop.HOME_CARE_PERSONAS[1],
                judgement=make_judgement(90.0, "Spouse feedback."),
            ),
        ]
        aggregate = rsa_spec_loop.aggregate_persona_judgements(persona_judgements)
        payload = json.loads(aggregate.raw_response)

        self.assertEqual(aggregate.total_score, 85.0)
        self.assertEqual(len(payload["persona_judgements"]), 2)
        self.assertIn("Adult-child feedback.", aggregate.private_feedback)
        self.assertIn("Spouse feedback.", aggregate.private_feedback)

    def test_socratic_search_can_archive_novel_non_winning_candidate(self) -> None:
        retained = should_retain_candidate(
            score=70.0,
            score_before=71.0,
            constraint_pass=True,
            novelty_score=1.0,
        )
        self.assertTrue(retained)


if __name__ == "__main__":
    unittest.main()
