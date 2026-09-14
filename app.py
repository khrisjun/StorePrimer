#!/usr/bin/env python3
from __future__ import annotations

import html
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from issuu_to_pdf import DEFAULT_ISSUU_URL, convert_issuu_to_searchable_pdf


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _render_form(error_message: str = "", default_url: str = DEFAULT_ISSUU_URL) -> bytes:
    escaped_default_url = html.escape(default_url, quote=True)
    escaped_error = html.escape(error_message)
    error_section = (
        f"<p style='color:#b91c1c;font-weight:600'>{escaped_error}</p>" if error_message else ""
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Issuu to searchable PDF</title>
</head>
<body style="font-family: sans-serif; margin: 2rem;">
  <h1>Issuu to searchable PDF</h1>
  <p>Paste an Issuu URL, then download the generated searchable PDF.</p>
  {error_section}
  <form method="post" action="/convert">
    <label for="issuu_url">Issuu URL</label><br />
    <input id="issuu_url" name="issuu_url" type="url" required style="width: min(100%, 52rem);" value="{escaped_default_url}" />
    <br /><br />
    <button type="submit">Convert and download</button>
  </form>
</body>
</html>
"""
    return page.encode("utf-8")


def _response(
    status: str,
    body: bytes,
    headers: list[tuple[str, str]] | None = None,
) -> tuple[str, list[tuple[str, str]], Iterable[bytes]]:
    resolved_headers = headers or []
    resolved_headers.append(("Content-Length", str(len(body))))
    return status, resolved_headers, [body]


def application(environ: dict, start_response) -> Iterable[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/":
        status, headers, body = _response(
            "200 OK",
            _render_form(),
            [("Content-Type", "text/html; charset=utf-8")],
        )
        start_response(status, headers)
        return body

    if method == "POST" and path == "/convert":
        content_length = int(environ.get("CONTENT_LENGTH", "0") or "0")
        raw_payload = environ.get("wsgi.input", io.BytesIO()).read(content_length)
        form = parse_qs(raw_payload.decode("utf-8"), keep_blank_values=True)
        issuu_url = (form.get("issuu_url", [""])[0] or "").strip()

        if not _is_valid_http_url(issuu_url):
            status, headers, body = _response(
                "400 Bad Request",
                _render_form("Please provide a valid Issuu URL.", issuu_url),
                [("Content-Type", "text/html; charset=utf-8")],
            )
            start_response(status, headers)
            return body

        try:
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                output_pdf = temp_path / "output.pdf"
                result = convert_issuu_to_searchable_pdf(
                    issuu_url=issuu_url,
                    output_pdf=output_pdf,
                    workdir=temp_path / "work",
                    keep_images=False,
                )
                payload = result.read_bytes()
        except Exception:  # noqa: BLE001
            status, headers, body = _response(
                "500 Internal Server Error",
                _render_form("Conversion failed. Check the URL and try again."),
                [("Content-Type", "text/html; charset=utf-8")],
            )
            start_response(status, headers)
            return body

        filename = "issuu-output.pdf"
        status, headers, body = _response(
            "200 OK",
            payload,
            [
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", f'attachment; filename="{filename}"'),
            ],
        )
        start_response(status, headers)
        return body

    status, headers, body = _response(
        "404 Not Found",
        b"Not Found",
        [("Content-Type", "text/plain; charset=utf-8")],
    )
    start_response(status, headers)
    return body


app = application


def main() -> int:
    from wsgiref.simple_server import make_server

    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "7860"))
    print(f"Serving on http://{host}:{port}")
    with make_server(host, port, application) as server:
        server.serve_forever()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
