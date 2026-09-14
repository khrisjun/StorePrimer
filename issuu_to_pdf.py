#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "StorePrimer-IssuuToPDF/1.0"
DEFAULT_ISSUU_URL = "https://issuu.com/focusathenley/docs/msa_primer_pre-publication_v1"


def fetch_html(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_document_metadata(html: str) -> dict[str, Any]:
    metadata = _extract_from_json_blob(html)
    if metadata:
        return metadata

    document_id = _extract_first_match(
        html,
        [
            r'"documentId"\s*:\s*"([^"]+)"',
            r'"id"\s*:\s*"([0-9a-f]{16,64})"',
        ],
    )
    if not document_id:
        raise ValueError("Unable to find Issuu document id in page HTML.")

    page_count_raw = _extract_first_match(
        html,
        [
            r'"pageCount"\s*:\s*(\d+)',
            r'"pages"\s*:\s*(\d+)',
        ],
    )
    if not page_count_raw:
        raise ValueError("Unable to find Issuu page count in page HTML.")

    title = _extract_first_match(
        html,
        [
            r'"title"\s*:\s*"([^"]+)"',
            r"<title>([^<]+)</title>",
        ],
    ) or "issuu-document"

    return {
        "document_id": document_id,
        "page_count": int(page_count_raw),
        "title": _clean_title(title),
    }


def _extract_from_json_blob(html: str) -> dict[str, Any] | None:
    marker = "window.__INITIAL_STATE__"
    if marker not in html:
        return None

    start = html.find(marker)
    snippet = html[start : start + 300_000]
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;", snippet, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    def walk(node: Any) -> tuple[str | None, int | None, str | None]:
        if isinstance(node, dict):
            document_id = None
            page_count = None
            title = None

            for key, value in node.items():
                lowered = key.lower()
                if document_id is None and lowered in {"documentid", "document_id"} and isinstance(value, str):
                    document_id = value
                if page_count is None and lowered in {"pagecount", "page_count", "pages"} and isinstance(value, int):
                    page_count = value
                if title is None and lowered == "title" and isinstance(value, str):
                    title = value

                child_document_id, child_page_count, child_title = walk(value)
                document_id = document_id or child_document_id
                page_count = page_count or child_page_count
                title = title or child_title

            return document_id, page_count, title

        if isinstance(node, list):
            found_document_id = None
            found_page_count = None
            found_title = None
            for item in node:
                child_document_id, child_page_count, child_title = walk(item)
                found_document_id = found_document_id or child_document_id
                found_page_count = found_page_count or child_page_count
                found_title = found_title or child_title
            return found_document_id, found_page_count, found_title

        return None, None, None

    document_id, page_count, title = walk(data)
    if not document_id or not page_count:
        return None

    return {
        "document_id": document_id,
        "page_count": page_count,
        "title": _clean_title(title or "issuu-document"),
    }


def _extract_first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _clean_title(title: str) -> str:
    title = title.strip()
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"[\u0000-\u001f]", "", title)
    return title


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned.strip("_") or "issuu-document"


def derive_output_basename(issuu_url: str, fallback_title: str) -> str:
    parsed = urllib.parse.urlparse(issuu_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if "docs" in segments:
        docs_index = segments.index("docs")
        if docs_index + 1 < len(segments):
            return sanitize_filename(segments[docs_index + 1])
    if segments:
        return sanitize_filename(segments[-1])
    return sanitize_filename(fallback_title)


def build_page_image_urls(document_id: str, page_number: int) -> list[str]:
    return [
        f"https://image.isu.pub/{document_id}/jpg/page_{page_number}.jpg",
        f"https://image.isu.pub/{document_id}/png/page_{page_number}.png",
    ]


def download_page_images(document_id: str, page_count: int, pages_dir: Path, timeout: int = 30) -> list[Path]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    for page_number in range(1, page_count + 1):
        output_path = pages_dir / f"page_{page_number:04d}.jpg"
        success = False
        for image_url in build_page_image_urls(document_id, page_number):
            request = urllib.request.Request(image_url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read()
            except urllib.error.URLError:
                continue

            output_path.write_bytes(payload)
            success = True
            break

        if not success:
            raise RuntimeError(f"Failed to download image for page {page_number}.")
        downloaded.append(output_path)

    return downloaded


def create_searchable_pdf(image_paths: list[Path], output_pdf: Path, working_dir: Path) -> None:
    try:
        import pytesseract
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependencies. Install with: pip install pytesseract pypdf pillow "
            "and ensure the tesseract binary is installed."
        ) from exc

    ocr_dir = working_dir / "ocr-pages"
    ocr_dir.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    for image_path in image_paths:
        page_pdf_path = ocr_dir / f"{image_path.stem}.pdf"
        page_pdf_bytes = pytesseract.image_to_pdf_or_hocr(str(image_path), extension="pdf")
        page_pdf_path.write_bytes(page_pdf_bytes)
        reader = PdfReader(str(page_pdf_path))
        writer.add_page(reader.pages[0])

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as handle:
        writer.write(handle)


def convert_issuu_to_searchable_pdf(
    issuu_url: str,
    output_pdf: Path | None = None,
    workdir: Path | None = None,
    keep_images: bool = False,
) -> Path:
    html = fetch_html(issuu_url)
    metadata = extract_document_metadata(html)
    doc_id = metadata["document_id"]
    page_count = metadata["page_count"]
    title = metadata["title"]
    output_basename = derive_output_basename(issuu_url, title)

    if output_pdf is None:
        output_pdf = Path.cwd() / f"{output_basename}.pdf"
    if workdir is None:
        workdir = Path.cwd() / f"{output_basename}_work"

    pages_dir = workdir / "pages"
    images = download_page_images(doc_id, page_count, pages_dir)
    create_searchable_pdf(images, output_pdf, workdir)

    if not keep_images and workdir.exists():
        shutil.rmtree(workdir)

    return output_pdf


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Issuu flipbook pages and create a searchable OCR PDF."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_ISSUU_URL,
        help="Issuu document URL. Defaults to the MSA Primer first-pass document.",
    )
    parser.add_argument("--output", help="Path to output PDF.")
    parser.add_argument(
        "--workdir",
        help="Working directory for downloaded page images and OCR page PDFs.",
    )
    parser.add_argument(
        "--keep-images",
        action="store_true",
        help="Keep intermediate downloaded images and OCR pages.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = Path(args.output).resolve() if args.output else None
    workdir = Path(args.workdir).resolve() if args.workdir else None

    try:
        result_path = convert_issuu_to_searchable_pdf(
            issuu_url=args.url,
            output_pdf=output_path,
            workdir=workdir,
            keep_images=args.keep_images,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Searchable PDF created: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
