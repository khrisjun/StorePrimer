import unittest

from issuu_to_pdf import build_page_image_urls, extract_document_metadata, sanitize_filename


class IssuuToPdfTests(unittest.TestCase):
    def test_extract_document_metadata_from_direct_fields(self) -> None:
        html = """
        <html><head><title>My Primer</title></head><body>
        {"documentId":"abc123def456","pageCount":42}
        </body></html>
        """
        metadata = extract_document_metadata(html)
        self.assertEqual(metadata["document_id"], "abc123def456")
        self.assertEqual(metadata["page_count"], 42)
        self.assertEqual(metadata["title"], "My Primer")

    def test_extract_document_metadata_from_initial_state_blob(self) -> None:
        html = """
        <script>
        window.__INITIAL_STATE__ = {
          "publication": {
            "documentId": "xyz987",
            "pageCount": 8,
            "title": "MSA Primer"
          }
        };
        </script>
        """
        metadata = extract_document_metadata(html)
        self.assertEqual(metadata["document_id"], "xyz987")
        self.assertEqual(metadata["page_count"], 8)
        self.assertEqual(metadata["title"], "MSA Primer")

    def test_build_page_image_urls(self) -> None:
        urls = build_page_image_urls("docid", 3)
        self.assertEqual(
            urls,
            [
                "https://image.isu.pub/docid/jpg/page_3.jpg",
                "https://image.isu.pub/docid/png/page_3.png",
            ],
        )

    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename(" MSA Primer: v1 "), "MSA_Primer_v1")


if __name__ == "__main__":
    unittest.main()
