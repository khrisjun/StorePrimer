import io
import unittest
from unittest.mock import patch

from app import _CONVERTED_OUTPUTS, app, application


class AppTests(unittest.TestCase):
    def test_app_alias_points_to_wsgi_application(self) -> None:
        self.assertIs(app, application)

    def _request(self, method: str, path: str, body: bytes = b"") -> tuple[str, dict[str, str], bytes]:
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
        response: dict[str, object] = {"status": "", "headers": []}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            response["status"] = status
            response["headers"] = headers

        chunks = list(application(environ, start_response))
        merged_headers = {key: value for key, value in response["headers"]}  # type: ignore[index]
        return response["status"], merged_headers, b"".join(chunks)  # type: ignore[return-value]

    def test_get_root_renders_form(self) -> None:
        status, headers, body = self._request("GET", "/")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Issuu URL", body)

    def test_post_convert_with_invalid_url_returns_error(self) -> None:
        status, headers, body = self._request("POST", "/convert", b"issuu_url=not-a-url")
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Please provide a valid Issuu URL", body)

    def test_post_convert_returns_pdf(self) -> None:
        self.addCleanup(_CONVERTED_OUTPUTS.clear)
        with patch("app.convert_issuu_to_searchable_pdf") as convert:
            convert.return_value.read_bytes.return_value = b"%PDF-1.7 test"
            with patch("app.secrets.token_urlsafe", return_value="token-123"):
                status, headers, body = self._request(
                    "POST",
                    "/convert",
                    b"issuu_url=https%3A%2F%2Fissuu.com%2Ffocusathenley%2Fdocs%2Fmsa_primer_pre-publication_v1",
                )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Download output document", body)
        self.assertEqual(_CONVERTED_OUTPUTS["token-123"], b"%PDF-1.7 test")

    def test_post_download_returns_pdf_and_consumes_token(self) -> None:
        _CONVERTED_OUTPUTS["token-xyz"] = b"%PDF-1.7 test"
        self.addCleanup(_CONVERTED_OUTPUTS.clear)
        status, headers, body = self._request(
            "POST",
            "/download",
            b"download_token=token-xyz",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(headers["Content-Disposition"], 'attachment; filename="issuu-output.pdf"')
        self.assertEqual(body, b"%PDF-1.7 test")
        self.assertNotIn("token-xyz", _CONVERTED_OUTPUTS)

    def test_post_download_with_invalid_token_returns_error(self) -> None:
        status, headers, body = self._request(
            "POST",
            "/download",
            b"download_token=missing",
        )
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Please process again", body)

    def test_get_root_process_button_label(self) -> None:
        status, headers, body = self._request("GET", "/")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b">Process<", body)


if __name__ == "__main__":
    unittest.main()
