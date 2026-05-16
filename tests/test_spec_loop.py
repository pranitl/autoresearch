import json
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import spec_loop


ROOT = Path(__file__).resolve().parents[1]
PAGE_SPEC = (ROOT / "page_spec.md").read_text(encoding="utf-8")
SPEC_PROGRAM = (ROOT / "spec_program.md").read_text(encoding="utf-8")
SCORING_RUBRIC = (ROOT / "scoring_rubric.md").read_text(encoding="utf-8")


class SpecLoopTests(unittest.TestCase):
    def test_extract_json_object_from_code_fence(self) -> None:
        raw = "before\n```json\n{\"ok\": true, \"score\": 71}\n```\nafter"
        payload = spec_loop.extract_json_object(raw)
        self.assertEqual(payload, '{"ok": true, "score": 71}')

    def test_parse_mutation_tagged_response(self) -> None:
        raw = (
            "<mutation>\n"
            '{"changed_section":"Hero","change_summary":"Tightened the headline."}\n'
            "</mutation>\n"
            "<updated_section>\n"
            "1. Hero\n"
            "   Headline: Faster headline\n"
            "</updated_section>\n"
        )
        mutation = spec_loop.parse_mutation(raw)
        self.assertEqual(mutation.changed_section, "Hero")
        self.assertEqual(mutation.change_summary, "Tightened the headline.")
        self.assertEqual(
            mutation.updated_section,
            "1. Hero\n   Headline: Faster headline\n",
        )

    def test_validate_candidate_accepts_single_hero_change(self) -> None:
        candidate = re.sub(
            r"(?m)^(\s*Hero Keyword:\s*).+$",
            r"\1Trusted Home Care",
            PAGE_SPEC,
            count=1,
        )
        normalized, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Hero",
            current_score=68.0,
        )
        self.assertFalse(errors)
        self.assertIn("Current champion score: 68/100", normalized)

    def test_validate_candidate_rejects_multiple_section_changes(self) -> None:
        candidate = re.sub(
            r"(?m)^(\s*Hero Keyword:\s*).+$",
            r"\1Trusted Home Care",
            PAGE_SPEC,
            count=1,
        ).replace(
            "Selected page: About us",
            "Selected page: Resources",
        )
        _, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Hero",
            current_score=68.0,
        )
        self.assertTrue(any("Exactly one editable section may change" in item for item in errors))

    def test_validate_services_section_rejects_duplicate_services(self) -> None:
        candidate = PAGE_SPEC.replace(
            "- Veteran Care",
            "- Dementia Care",
        )
        _, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Services Grid",
            current_score=68.0,
        )
        self.assertTrue(any("duplicate services" in item.lower() for item in errors))

    def test_validate_featured_page_section_rejects_markdown_and_overlong_text(self) -> None:
        replacement = (
            "[Learn more](https://example.com) "
            + "A" * 210
        )
        candidate = PAGE_SPEC.replace(
            "We find the right caregiver for your loved one—personality, needs, and schedule. Meet our compassionate team and see why families across Boston Northwest choose us.",
            replacement,
        )
        _, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Featured Page",
            current_score=68.0,
        )
        self.assertTrue(any("plain text only" in item.lower() for item in errors))
        self.assertTrue(any("exceeds 200 characters" in item.lower() for item in errors))

    def test_validate_featured_page_section_rejects_non_about_selection(self) -> None:
        candidate = PAGE_SPEC.replace(
            "Selected page: About us",
            "Selected page: Blog",
        )
        _, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Featured Page",
            current_score=68.0,
        )
        self.assertTrue(any("must remain 'About us'" in item for item in errors))

    def test_validate_candidate_rejects_section_outside_allowed_scope(self) -> None:
        candidate = re.sub(
            r"(?m)^(\s*Hero Keyword:\s*).+$",
            r"\1Trusted Home Care",
            PAGE_SPEC,
            count=1,
        )
        _, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Hero",
            current_score=68.0,
            allowed_sections=["Owners Section", "Services Grid", "Videos"],
        )
        self.assertTrue(any("must be one of" in item for item in errors))

    def test_validate_hero_section_rejects_auto_appended_location_duplication(self) -> None:
        candidate = re.sub(
            r"(?m)^(\s*Hero Keyword:\s*).+$",
            r"\1Trusted Home Care in Boston Northwest",
            PAGE_SPEC,
            count=1,
        )
        _, errors = spec_loop.validate_candidate_spec(
            current_spec=PAGE_SPEC,
            candidate_spec=candidate,
            declared_section="Hero",
            current_score=68.0,
        )
        self.assertTrue(any("should not repeat 'Boston Northwest'" in item for item in errors))

    def test_replace_current_champion_score_rounds_to_tenth(self) -> None:
        updated = spec_loop.replace_current_champion_score(PAGE_SPEC, 72.04)
        self.assertIn("Current champion score: 72/100", updated)
        updated = spec_loop.replace_current_champion_score(PAGE_SPEC, 72.06)
        self.assertIn("Current champion score: 72.1/100", updated)

    def test_splice_updated_section_only_changes_target_section(self) -> None:
        candidate = spec_loop.splice_updated_section(
            PAGE_SPEC,
            "Hero",
            "1. Hero\n   Hero Keyword: Home Care With No Weekly Minimums\n",
        )
        self.assertEqual(spec_loop.find_changed_sections(PAGE_SPEC, candidate), ["Hero"])
        self.assertIn("Hero Keyword: Home Care With No Weekly Minimums", candidate)

    def test_build_mutator_prompt_uses_program_file(self) -> None:
        messages = spec_loop.build_mutator_prompt(
            program_text=SPEC_PROGRAM,
            target_file_name="page_spec.md",
            spec_text=PAGE_SPEC,
            champion_score=68.0,
            round_number=1,
            accepted_summaries=[],
            recent_rejections=[],
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Follow the provided program file", messages[0]["content"])
        self.assertIn("<program>", messages[1]["content"])
        self.assertIn("You are running an autonomous copy-optimization loop", messages[1]["content"])
        self.assertIn("Target file to edit: page_spec.md", messages[1]["content"])
        self.assertIn("Return only the single updated section", messages[1]["content"])
        self.assertIn("Prior-round persona judge feedback:", messages[1]["content"])

    def test_build_mutator_prompt_includes_prior_persona_feedback(self) -> None:
        messages = spec_loop.build_mutator_prompt(
            program_text=SPEC_PROGRAM,
            target_file_name="page_spec.md",
            spec_text=PAGE_SPEC,
            champion_score=68.0,
            round_number=2,
            accepted_summaries=[],
            recent_rejections=[],
            prior_persona_feedback=[
                {
                    "persona_name": "The Overwhelmed Adult Child",
                    "total_score": 82,
                    "feedback": "Make crisis relief more concrete.",
                }
            ],
        )
        self.assertIn(
            "The Overwhelmed Adult Child (82/100): Make crisis relief more concrete.",
            messages[1]["content"],
        )

    def test_build_judge_prompt_uses_external_rubric(self) -> None:
        messages = spec_loop.build_judge_prompt(
            spec_text=PAGE_SPEC,
            rubric_text=SCORING_RUBRIC,
            champion_score=34.0,
        )
        self.assertIn("<rubric>", messages[1]["content"])
        self.assertIn("Locked Scoring Rubric", messages[1]["content"])
        self.assertIn("Assigned persona judge:", messages[1]["content"])

    def test_parse_seo_gate_result(self) -> None:
        gate = spec_loop.parse_seo_gate_result(
            json.dumps(
                {
                    "passes": False,
                    "issues": ["Too generic."],
                    "repair_instructions": ["Add concrete onboarding detail."],
                    "risk_level": "medium",
                    "notes": "Needs specificity.",
                }
            )
        )
        self.assertFalse(gate.passes)
        self.assertEqual(gate.issues, ["Too generic."])
        self.assertEqual(gate.repair_instructions, ["Add concrete onboarding detail."])

    def test_aggregate_persona_judgements_equal_weights_scores(self) -> None:
        def make_judgement(total: float, feedback: str) -> spec_loop.Judgement:
            scores = {
                "hero_primary_cta_pull": total * 0.15,
                "service_grid_clickability": total * 0.15,
                "benefit_emotional_drive": total * 0.10,
                "trust_local_relevance": total * 0.10,
                "urgency_next_step_clarity": total * 0.10,
                "wordpress_compatibility": total * 0.10,
                "overall_ctr_potential": total * 0.30,
            }
            return spec_loop.Judgement(
                constraint_pass=True,
                violations=[],
                scores=scores,
                category_rationales={key: "ok" for key in scores},
                total_score=total,
                summary=f"{total}",
                raw_response="{}",
                private_feedback=feedback,
            )

        aggregate = spec_loop.aggregate_persona_judgements(
            [
                spec_loop.PersonaJudgement(
                    persona=spec_loop.HOME_CARE_PERSONAS[0],
                    judgement=make_judgement(80.0, "Adult-child feedback."),
                ),
                spec_loop.PersonaJudgement(
                    persona=spec_loop.HOME_CARE_PERSONAS[1],
                    judgement=make_judgement(90.0, "Spouse feedback."),
                ),
            ]
        )
        payload = json.loads(aggregate.raw_response)
        self.assertEqual(aggregate.total_score, 85.0)
        self.assertEqual(len(payload["persona_judgements"]), 2)
        self.assertIn("Adult-child feedback.", aggregate.private_feedback)

    def test_reasoning_config_parses_effort(self) -> None:
        with patch.dict("os.environ", {"OPENROUTER_JUDGE_REASONING_EFFORT": "xhigh"}, clear=False):
            self.assertEqual(
                spec_loop.get_reasoning_config("OPENROUTER_JUDGE_REASONING_EFFORT"),
                {"effort": "xhigh"},
            )

    def test_openrouter_client_includes_reasoning_payload(self) -> None:
        response = MagicMock()
        response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        response.raise_for_status.return_value = None
        with patch("spec_loop.requests.post", return_value=response) as mock_post:
            client = spec_loop.OpenRouterClient(api_key="test-key", base_url="https://openrouter.ai/api/v1")
            output = client.complete(
                model="openai/gpt-5.4",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                reasoning={"effort": "xhigh"},
            )
        self.assertEqual(output, "ok")
        self.assertEqual(mock_post.call_args.kwargs["json"]["reasoning"], {"effort": "xhigh"})

    def test_openrouter_client_raises_retryable_error_on_non_json_body(self) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.text = "<html>upstream error</html>"
        response.json.side_effect = ValueError("not json")
        with patch("spec_loop.requests.post", return_value=response):
            client = spec_loop.OpenRouterClient(api_key="test-key", base_url="https://openrouter.ai/api/v1")
            with self.assertRaises(spec_loop.SpecLoopError) as ctx:
                client.complete(
                    model="openai/gpt-5.4",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.2,
                )
        self.assertIn("non-JSON response", str(ctx.exception))

    def test_openrouter_client_wraps_timeout_as_spec_loop_error(self) -> None:
        with patch(
            "spec_loop.requests.post",
            side_effect=spec_loop.requests.exceptions.ReadTimeout("timed out"),
        ):
            client = spec_loop.OpenRouterClient(api_key="test-key", base_url="https://openrouter.ai/api/v1")
            with self.assertRaises(spec_loop.SpecLoopError) as ctx:
                client.complete(
                    model="openai/gpt-5.4",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.2,
                )
        self.assertIn("timed out after 300s", str(ctx.exception))

    def test_call_mutator_retries_after_client_error(self) -> None:
        client = MagicMock()
        client.complete.side_effect = [
            spec_loop.SpecLoopError("Unsupported OpenRouter content payload: None"),
            '<mutation>{"changed_section":"Hero","change_summary":"Tightened the hero."}</mutation>\n'
            "<updated_section>\n1. Hero\n   Hero Keyword: Trusted Home Care\n</updated_section>\n",
        ]
        mutation = spec_loop.call_mutator(
            client=client,
            model="minimax/minimax-m2.7",
            reasoning=None,
            program_text=SPEC_PROGRAM,
            target_file_name="page_spec.md",
            spec_text=PAGE_SPEC,
            champion_score=86.0,
            round_number=1,
            accepted_summaries=[],
            recent_rejections=[],
            allowed_sections=["Hero"],
            attempts=3,
            temperature=0.7,
        )
        self.assertEqual(mutation.changed_section, "Hero")
        self.assertEqual(client.complete.call_count, 2)

    def test_call_judge_retries_after_client_error(self) -> None:
        client = MagicMock()
        judge_payload = json.dumps(
            {
                "constraint_pass": True,
                "violations": [],
                "scores": {
                    "hero_primary_cta_pull": 12,
                    "service_grid_clickability": 11,
                    "benefit_emotional_drive": 8,
                    "trust_local_relevance": 10,
                    "urgency_next_step_clarity": 9,
                    "wordpress_compatibility": 10,
                    "overall_ctr_potential": 26,
                },
                "category_rationales": {
                    "hero_primary_cta_pull": "ok",
                    "service_grid_clickability": "ok",
                    "benefit_emotional_drive": "ok",
                    "trust_local_relevance": "ok",
                    "urgency_next_step_clarity": "ok",
                    "wordpress_compatibility": "ok",
                    "overall_ctr_potential": "ok",
                },
                "private_feedback": "Useful persona feedback.",
                "total_score": 86,
                "summary": "ok",
            }
        )
        client.complete.side_effect = [
            spec_loop.SpecLoopError("Unsupported OpenRouter content payload: None"),
            judge_payload,
            judge_payload,
            judge_payload,
            judge_payload,
        ]
        judgement = spec_loop.call_judge(
            client=client,
            model="openai/gpt-5.4",
            reasoning={"effort": "xhigh"},
            spec_text=PAGE_SPEC,
            rubric_text=SCORING_RUBRIC,
            champion_score=86.0,
            attempts=3,
            temperature=0.2,
        )
        self.assertTrue(judgement.constraint_pass)
        self.assertEqual(judgement.total_score, 86)
        self.assertEqual(client.complete.call_count, 5)


if __name__ == "__main__":
    unittest.main()
