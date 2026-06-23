# Receipt fonts

PDF receipts render Thai text, which needs a Thai-capable TTF. The resolver in
`app/pdf_receipt.py` looks for a bundled font here first, then falls back to common
system fonts (macOS Arial Unicode / Ayuthaya, Linux Noto Sans Thai).

For a portable production deploy, drop an OFL-licensed Thai font here, e.g.:

- `Sarabun-Regular.ttf` (https://fonts.google.com/specimen/Sarabun)
- `NotoSansThai-Regular.ttf` (https://fonts.google.com/noto/specimen/Noto+Sans+Thai)

These are not committed because of font licensing/size; the resolver works without
them on macOS, and on Linux if `fonts-noto` (or similar) is installed.
