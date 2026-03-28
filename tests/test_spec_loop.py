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
        candidate = PAGE_SPEC.replace(
            "Hero Keyword: Boston Northwest Home Care - Get Free Pricing Today",
            "Hero Keyword: Boston Northwest Home Care - Free Consult",
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
        candidate = PAGE_SPEC.replace(
            "Hero Keyword: Boston Northwest Home Care - Get Free Pricing Today",
            "Hero Keyword: Boston Northwest Home Care - Free Consult",
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
            "Meet the local care team families trust for compassionate support, no weekly minimums, and care plans built around your loved one. Learn what sets our Boston Northwest team apart.",
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

    def test_build_judge_prompt_uses_external_rubric(self) -> None:
        messages = spec_loop.build_judge_prompt(
            spec_text=PAGE_SPEC,
            rubric_text=SCORING_RUBRIC,
            champion_score=34.0,
        )
        self.assertIn("<rubric>", messages[1]["content"])
        self.assertIn("Locked Scoring Rubric", messages[1]["content"])

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


if __name__ == "__main__":
    unittest.main()
