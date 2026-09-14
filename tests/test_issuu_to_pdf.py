import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from issuu_to_pdf import (
    DEFAULT_ISSUU_URL,
    build_page_image_urls,
    convert_issuu_to_searchable_pdf,
    extract_document_metadata,
    parse_args,
    sanitize_filename,
)


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

    def test_extract_document_metadata_from_next_data_blob(self) -> None:
        html = """
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "publication": {
                "documentId": "next12345",
                "pageCount": 12,
                "title": "Next Primer"
              }
            }
          }
        }
        </script>
        """
        metadata = extract_document_metadata(html)
        self.assertEqual(metadata["document_id"], "next12345")
        self.assertEqual(metadata["page_count"], 12)
        self.assertEqual(metadata["title"], "Next Primer")

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

    def test_parse_args_uses_default_first_pass_url(self) -> None:
        args = parse_args([])
        self.assertEqual(args.url, DEFAULT_ISSUU_URL)

    def test_convert_uses_url_slug_for_default_output_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with (
                patch("issuu_to_pdf.fetch_html", return_value="<html></html>"),
                patch(
                    "issuu_to_pdf.extract_document_metadata",
                    return_value={
                        "document_id": "docid",
                        "page_count": 1,
                        "title": "Some Other Title",
                    },
                ),
                patch("issuu_to_pdf.download_page_images", return_value=[]),
                patch("issuu_to_pdf.create_searchable_pdf"),
                patch("issuu_to_pdf.Path.cwd", return_value=Path(temp_dir)),
            ):
                output_path = convert_issuu_to_searchable_pdf(
                    "https://issuu.com/focusathenley/docs/msa_primer_pre-publication_v1"
                )

        self.assertEqual(output_path.name, "msa_primer_pre-publication_v1.pdf")


if __name__ == "__main__":
    unittest.main()
