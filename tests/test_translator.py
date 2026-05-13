import unittest

import config
from translator import TranslationError, extract_json_array


class TranslatorTests(unittest.TestCase):
    def test_build_system_prompt_uses_target_language(self):
        prompt = config.build_system_prompt("Japanese")

        self.assertIn("Translations must be Japanese.", prompt)
        self.assertIn("only outputs JSON", prompt)

    def test_extract_json_array_accepts_plain_json(self):
        parsed = extract_json_array('[{"id":"a","translation":"你好"}]')

        self.assertEqual(parsed, [{"id": "a", "translation": "你好"}])

    def test_extract_json_array_strips_markdown_fence_and_extra_text(self):
        parsed = extract_json_array(
            'result:\n```json\n[{"id":"a","translation":"你好"}]\n```\n'
        )

        self.assertEqual(parsed, [{"id": "a", "translation": "你好"}])

    def test_extract_json_array_rejects_non_array(self):
        with self.assertRaises(TranslationError):
            extract_json_array('{"id":"a","translation":"你好"}')


if __name__ == "__main__":
    unittest.main()
