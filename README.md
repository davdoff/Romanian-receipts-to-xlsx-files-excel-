# Receipt / Invoice Parser

## Technical Summary

A two-stage document extraction pipeline designed for Romanian fiscal documents. Stage one uses **Google Cloud Vision** (document text detection) to OCR each page into raw text. Stage two sends that text to **Anthropic Claude Haiku** with a schema-anchored system prompt that forces structured JSON output. The JSON is then validated and written to a styled Excel workbook via **openpyxl**.

The pipeline accepts either a folder of images or a multi-page PDF (split via `pdf2image` + poppler). Two modes are supported: `receipts` (bonuri fiscale) and `facturi` (business invoices). Facturi mode includes prompt-side relevance filtering — the model decides whether each invoice matches the target vendor and the script skips non-matching pages without touching the code. Cost per document is approximately **$0.0015** (Claude Haiku pricing).

**APIs used:** Google Vision for OCR, Anthropic Claude Haiku for structured extraction. Any AI provider with a text-in / JSON-out API can replace the Anthropic side — these are simply the ones that have worked best for this use case so far.

---

## What This Does

You drop a PDF (or a folder of images) into the script and it produces a clean Excel spreadsheet with the data extracted from each page — no manual typing, no copy-pasting.

It handles two types of Romanian fiscal documents:
- **Receipts** (bonuri fiscale) — extracts receipt number, date, vendor, client, VAT breakdown, totals
- **Invoices** (facturi) — extracts invoice number, date, vendor, client, contract number, delivery period, total due

---

## Requirements

### System dependencies

**Python 3.10 or newer** — check what you have:
```bash
python3 --version
```

**Poppler** (needed to read PDFs) — install once:
```bash
# macOS
brew install poppler

# Windows — download from https://github.com/oschwartz10612/poppler-windows/releases
# then add the bin/ folder to your PATH
```

### Python packages

Install everything at once:
```bash
pip install -r requirements.txt
```

---

## API Keys

You need two API keys. Both should be set as environment variables on your machine — not stored in any file inside the project.

**Anthropic (Claude)** — get your key at console.anthropic.com
```bash
echo 'export ANTHROPIC_API_KEY=your-key-here' >> ~/.zshrc
source ~/.zshrc
```

**Google Cloud Vision** — get your key at console.cloud.google.com (enable the Cloud Vision API first)
```bash
echo 'export GOOGLE_VISION_API_KEY=your-key-here' >> ~/.zshrc
source ~/.zshrc
```

> On Windows, search "environment variables" in the Start menu and add them under System Properties → Environment Variables.

To verify the keys are set correctly, run:
```bash
echo $ANTHROPIC_API_KEY
echo $GOOGLE_VISION_API_KEY
```
Both should print your key (not blank).

---

## Folder Structure

```
Receipt parser/
├── Main.py
├── requirements.txt
├── output files/          ← Excel outputs land here automatically
├── tests/
│   └── inputs/
│       ├── Receipts/      ← put receipt images or PDFs here
│       └── Facturi/       ← put invoice PDFs here
```

The `output files/` folder must exist before running — create it once if it's not there:
```bash
mkdir "output files"
```

---

## How to Run

Open your terminal in the project folder, activate your virtual environment if you use one, then run:

**Process receipts:**
```bash
python Main.py --input tests/inputs/Receipts --mode receipts --output receipts.xlsx
```

**Process invoices:**
```bash
python Main.py --input tests/inputs/Facturi --mode facturi --output facturi.xlsx
```

**Process a single PDF:**
```bash
python Main.py --input tests/inputs/Facturi/myfile.pdf --mode facturi --output myfile.xlsx
```

The output file always lands in `output files/` regardless of what name you give it. If a document fails to parse and you want the script to keep going instead of stopping:
```bash
python Main.py --input ... --mode ... --skip-errors
```

---

## How Prompts and Outputs Work

This is the key to adapting the script to a different job. You don't need to change any logic — only the prompt constant and the Excel columns.

### The prompt structure

Each document type has a prompt constant at the top of `Main.py` (`RECEIPT_SYSTEM_PROMPT` and `FACTURA_SYSTEM_PROMPT`). Every prompt follows the same pattern:

```
1. One sentence describing the document type
2. SCHEMA block — the exact JSON shape the model must return
3. RULES block — field-by-field instructions
```

The model reads the schema first, so it knows the output shape before it reads any rules. Rules are short and imperative — no examples, no padding.

### Defining output fields

Each key in the SCHEMA becomes a column in Excel. To add a field:
1. Add it to the SCHEMA block in the prompt
2. Add a rule describing where to find it on the document
3. Add it to the `row_values` list in the matching `build_excel_*` function
4. Add a column header to the `headers` list

### Prompt-side filtering (the `relevant` field)

The factura prompt includes a `relevant` field. The model sets it to `true` or `false` based on a rule you define in the prompt (currently: vendor must contain "PPC Energie"). The script automatically skips any invoice where `relevant` is `false`.

To target a different vendor or document type, you only change this one rule:
```
- relevant: set to true only if the vendor name contains "Your Target Vendor"
```
No code changes needed.

### Changing the AI model

The model is set in `_call_api()`:
```python
model="claude-haiku-4-5-20251001"
```
You can swap this for any model ID from Anthropic (e.g. `claude-sonnet-4-5` for higher accuracy at higher cost). If you want to use a completely different AI provider, replace the `_call_api()` function — the inputs are `ocr_text` (a string) and `system_prompt` (a string), and it must return a Python dict parsed from JSON.

---

## Troubleshooting

**"Set ANTHROPIC_API_KEY environment variable first"**
Your key isn't loaded. Run `echo $ANTHROPIC_API_KEY` — if it's blank, re-run the `echo >> ~/.zshrc` step and open a new terminal.

**"No supported images found"**
The folder path is wrong, or the files are a format the script doesn't support. Supported: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.pdf`.

**"pdf2image is not installed"**
Run `pip install pdf2image` and make sure poppler is installed (see System dependencies above).

**Parse errors on some pages**
Some pages may be blurry, rotated, or have unusual layouts. Use `--skip-errors` to process the rest and check the "Parse Error" column in the output Excel for details.
