import unittest

from provider_tools import normalize_base_url


class ProviderToolsTests(unittest.TestCase):
    def test_normalize_base_url_trims_trailing_slash(self):
        self.assertEqual(
            normalize_base_url(" https://api.example.com/v1/ "),
            "https://api.example.com/v1",
        )

    def test_normalize_base_url_collapses_duplicate_v1_suffix(self):
        self.assertEqual(
            normalize_base_url("https://api.example.com/v1/v1"),
            "https://api.example.com/v1",
        )

    def test_normalize_base_url_keeps_openai_compatible_nested_path(self):
        self.assertEqual(
            normalize_base_url("https://generativelanguage.googleapis.com/v1beta/openai/"),
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )


if __name__ == "__main__":
    unittest.main()
