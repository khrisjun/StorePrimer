# StorePrimer

## Issuu flipbook to searchable PDF

This repository includes a minimal script that:
1. Loads an Issuu document page
2. Extracts document metadata (document ID + page count)
3. Downloads an image for each page
4. OCRs each page into a searchable text-layer PDF
5. Merges all pages into one final document

It also includes a minimal web app (`app.py`) with a form where you can paste an Issuu URL and directly download the generated PDF.

### Requirements

- Python 3.9+
- Tesseract OCR binary installed on the host
- Python packages:
  - `pytesseract`
  - `pypdf`
  - `pillow`

Install packages:

```bash
pip install pytesseract pypdf pillow
```

### Usage

```bash
python /home/runner/work/StorePrimer/StorePrimer/issuu_to_pdf.py
```

By default the script uses `https://issuu.com/focusathenley/docs/msa_primer_pre-publication_v1`
and writes `msa_primer_pre-publication_v1.pdf` in the current directory.

Or pass explicit inputs:

```bash
python /home/runner/work/StorePrimer/StorePrimer/issuu_to_pdf.py \
  --url "https://issuu.com/focusathenley/docs/msa_primer_pre-publication_v1" \
  --output "/home/runner/work/StorePrimer/StorePrimer/msa_primer_pre-publication_v1.pdf"
```

Optional flags:
- `--workdir <path>` to keep intermediate files in a chosen location
- `--keep-images` to avoid deleting intermediate downloaded/OCR files

### Web app usage

Run:

```bash
python /home/runner/work/StorePrimer/StorePrimer/app.py
```

Then open `http://localhost:7860`, paste the Issuu URL, and click **Convert and download**.

### Deploying the interactive app

This repository includes a `Procfile` (`web: python app.py`) so platforms that run Procfile-based web services start the interactive app instead of showing repository docs.