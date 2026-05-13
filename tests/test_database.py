import tempfile
import unittest
from pathlib import Path

from database import bulk_get, init_db, make_cache_key, make_prompt_hash, set_many


class DatabaseTests(unittest.TestCase):
    def test_prompt_hash_is_stable_for_empty_and_whitespace(self):
        self.assertEqual(make_prompt_hash(""), make_prompt_hash("   "))

    def test_cache_key_changes_when_prompt_hash_changes(self):
        base = {
            "text_hash": "text",
            "model": "model-a",
            "prompt_version": "v1",
            "params_json": '{"temperature":0.7}',
        }
        key_a = make_cache_key(**base, prompt_hash=make_prompt_hash(""))
        key_b = make_cache_key(**base, prompt_hash=make_prompt_hash("literal style"))

        self.assertNotEqual(key_a, key_b)

    def test_bulk_get_and_set_many_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "translations.sqlite3")
            init_db(db_path)

            set_many(
                db_path,
                [
                    {
                        "cache_key": "cache-1",
                        "text_hash": "hash-1",
                        "model": "model-a",
                        "prompt_version": "v1",
                        "params_json": "{}",
                        "translation": "译文",
                        "created_at": 1,
                    }
                ],
            )

            self.assertEqual(
                bulk_get(db_path, ["cache-1", "missing"]),
                {"cache-1": "译文"},
            )


if __name__ == "__main__":
    unittest.main()
