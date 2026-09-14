import io
import unittest
from unittest.mock import patch

from app import application


class AppTests(unittest.TestCase):
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
        with patch("app.convert_issuu_to_searchable_pdf") as convert:
            convert.return_value.read_bytes.return_value = b"%PDF-1.7 test"
            status, headers, body = self._request(
                "POST",
                "/convert",
                b"issuu_url=https%3A%2F%2Fissuu.com%2Ffocusathenley%2Fdocs%2Fmsa_primer_pre-publication_v1",
            )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(body, b"%PDF-1.7 test")


if __name__ == "__main__":
    unittest.main()
