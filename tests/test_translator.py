import asyncio
import json
import unittest

import config
import translator
from translator import (
    TranslationError,
    build_chat_payload,
    extract_json_array,
    sample_blocks_for_glossary,
    split_text_for_translation,
)
from translation_types import TranslationOptions


def _extract_passages_json(content: str) -> list:
    start = content.find("[")
    end = content.rfind("]")
    return json.loads(content[start : end + 1])


def _translation_options(batch_size: int = 1) -> TranslationOptions:
    return TranslationOptions(
        api_key="key",
        base_url="https://api.example.com/v1",
        model="unknown-model",
        temperature=0,
        batch_size=batch_size,
        concurrency=1,
    )


class TranslatorTests(unittest.TestCase):
    def test_build_system_prompt_uses_target_language(self):
        prompt = config.build_system_prompt("Japanese")

        self.assertIn("Translations must be written in Japanese.", prompt)
        self.assertIn("only output strict JSON", prompt)

    def test_build_system_prompt_accepts_custom_target_language(self):
        prompt = config.build_system_prompt("Traditional Chinese")

        self.assertIn("Translations must be written in Traditional Chinese.", prompt)

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

    def test_chat_payload_omits_thinking_for_standard_provider_when_disabled(self):
        payload = build_chat_payload(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[],
            base_url="https://api.openai.com/v1",
            thinking_enabled=False,
        )

        self.assertNotIn("enable_thinking", payload)

    def test_chat_payload_disables_thinking_for_qwen_by_default(self):
        payload = build_chat_payload(
            model="qwen-plus",
            temperature=0.7,
            messages=[],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            thinking_enabled=False,
        )

        self.assertIs(payload["enable_thinking"], False)

    def test_chat_payload_enables_thinking_when_requested(self):
        payload = build_chat_payload(
            model="thinking-model",
            temperature=0.7,
            messages=[],
            base_url="https://api.example.com/v1",
            thinking_enabled=True,
        )

        self.assertIs(payload["enable_thinking"], True)

    def test_split_text_for_translation_splits_long_text(self):
        text = "First sentence. Second sentence. Third sentence."
        chunks = split_text_for_translation(text, max_tokens=3, model="unknown-model")

        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), text)

    def test_sample_blocks_for_glossary_uses_whole_short_book(self):
        blocks = [
            {"block_id": "a", "text": "Alpha"},
            {"block_id": "b", "text": "Beta"},
        ]

        self.assertEqual(sample_blocks_for_glossary(blocks, max_chars=100), ["Alpha", "Beta"])

    def test_sample_blocks_for_glossary_covers_front_middle_and_back(self):
        blocks = [
            {"block_id": f"b-{index}", "text": f"Block {index} text"}
            for index in range(12)
        ]

        samples = sample_blocks_for_glossary(blocks, max_chars=60)
        joined = "\n".join(samples)

        self.assertIn("Block 0 text", joined)
        self.assertIn("Block 4 text", joined)
        self.assertIn("Block 8 text", joined)

    def test_translate_batches_reassembles_split_block(self):
        original_call_model = translator._call_model
        original_max_tokens = config.MAX_BLOCK_TOKENS

        async def fake_call_model(_client, payload):
            content = payload["messages"][1]["content"]
            items = _extract_passages_json(content)
            return json.dumps(
                [
                    {"id": item["id"], "translation": f"T({item['text']})"}
                    for item in items
                ],
                ensure_ascii=False,
            )

        try:
            translator._call_model = fake_call_model
            config.MAX_BLOCK_TOKENS = 3
            results, failures = asyncio.run(
                translator.translate_batches(
                    [{"block_id": "block-1", "text": "First sentence. Second sentence."}],
                    _translation_options(),
                )
            )
        finally:
            translator._call_model = original_call_model
            config.MAX_BLOCK_TOKENS = original_max_tokens

        self.assertEqual(failures, [])
        self.assertGreater(results["block-1"].count("T("), 1)
        self.assertIn("\n", results["block-1"])

    def test_translate_batches_splits_bad_batch_and_recovers(self):
        original_call_model = translator._call_model

        async def fake_call_model(_client, payload):
            content = payload["messages"][1]["content"]
            items = _extract_passages_json(content)
            if len(items) > 1:
                return json.dumps(
                    [{"id": items[0]["id"], "translation": "partial"}],
                    ensure_ascii=False,
                )
            return json.dumps(
                [{"id": items[0]["id"], "translation": f"T({items[0]['text']})"}],
                ensure_ascii=False,
            )

        try:
            translator._call_model = fake_call_model
            results, failures = asyncio.run(
                translator.translate_batches(
                    [
                        {"block_id": "block-1", "text": "First."},
                        {"block_id": "block-2", "text": "Second."},
                    ],
                    _translation_options(batch_size=2),
                )
            )
        finally:
            translator._call_model = original_call_model

        self.assertEqual(failures, [])
        self.assertEqual(results, {"block-1": "T(First.)", "block-2": "T(Second.)"})


if __name__ == "__main__":
    unittest.main()
