import unittest

from backend.crawler import CrawlError, normalize_url, same_origin


class URLValidationTests(unittest.TestCase):
    def test_normalize_removes_fragment_and_adds_path(self):
        self.assertEqual(
            normalize_url("https://example.com#section"),
            "https://example.com/",
        )

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(CrawlError):
            normalize_url("file:///etc/passwd")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(CrawlError):
            normalize_url("https://user:pass@example.com")

    def test_same_origin_ignores_path(self):
        self.assertTrue(
            same_origin("https://example.com/start", "https://example.com/next")
        )

    def test_different_subdomain_is_not_same_origin(self):
        self.assertFalse(
            same_origin("https://example.com", "https://www.example.com")
        )


if __name__ == "__main__":
    unittest.main()
