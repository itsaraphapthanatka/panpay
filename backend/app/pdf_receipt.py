"""Generate a PDF receipt for a paid/refunded charge.

Thai text needs a Thai-capable TTF. We resolve one at runtime (bundled font first,
then common system fonts) and fall back to Helvetica if none is found.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Charge

_FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# (path, subfontIndex) candidates, best first.
_CANDIDATES: list[tuple[str, int]] = [
    (str(_FONTS_DIR / "Sarabun-Regular.ttf"), 0),
    (str(_FONTS_DIR / "NotoSansThai-Regular.ttf"), 0),
    ("/Library/Fonts/Arial Unicode.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Ayuthaya.ttf", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf", 0),
    ("/usr/share/fonts/truetype/tlwg/Sarabun.ttf", 0),
]

_FONT = "Helvetica"  # fallback
_resolved = False


def _ensure_font() -> str:
    global _FONT, _resolved
    if _resolved:
        return _FONT
    _resolved = True
    for path, idx in _CANDIDATES:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("PanThai", path, subfontIndex=idx))
                _FONT = "PanThai"
                break
            except Exception:
                continue
    return _FONT


def _baht(n) -> str:
    return "฿" + f"{float(n):,.2f}"


def _fmt(dt) -> str:
    return dt.strftime("%d/%m/%Y %H:%M") if dt else "-"


def generate_receipt_pdf(charge: Charge) -> bytes:
    font = _ensure_font()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A5,
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"Receipt {charge.id}",
    )

    h1 = ParagraphStyle("h1", fontName=font, fontSize=16, leading=20, textColor=colors.HexColor("#0f172a"))
    sub = ParagraphStyle("sub", fontName=font, fontSize=10, leading=14, textColor=colors.HexColor("#64748b"))
    label = ParagraphStyle("label", fontName=font, fontSize=9, textColor=colors.HexColor("#64748b"))
    val = ParagraphStyle("val", fontName=font, fontSize=10, textColor=colors.HexColor("#0f172a"))
    total = ParagraphStyle("total", fontName=font, fontSize=18, textColor=colors.HexColor("#16a34a"))

    p = charge.payment
    refunded = charge.status == "refunded"
    title = "ใบเสร็จรับเงิน / RECEIPT" + ("  (คืนเงินแล้ว / REFUNDED)" if refunded else "")

    elems = [
        Paragraph(charge.merchant.business_name, h1),
        Paragraph(title, sub),
        Spacer(1, 8 * mm),
    ]

    meta = [
        ["เลขที่ / No.", charge.id],
        ["วันที่ชำระ / Paid", _fmt(charge.paid_at)],
        ["อ้างอิง / Ref", charge.reference or "-"],
    ]
    meta_tbl = Table([[Paragraph(k, label), Paragraph(v, val)] for k, v in meta], colWidths=[45 * mm, None])
    meta_tbl.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    elems += [meta_tbl, Spacer(1, 6 * mm)]

    # Line item
    item_tbl = Table(
        [[Paragraph("รายการ / Item", label), Paragraph("จำนวน / Amount", label)],
         [Paragraph(charge.description or "ชำระเงิน / Payment", val), Paragraph(_baht(charge.amount), val)]],
        colWidths=[None, 40 * mm],
    )
    item_tbl.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#e6eaf2")),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#e6eaf2")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems += [item_tbl, Spacer(1, 4 * mm)]

    elems += [
        Table([[Paragraph("รวมทั้งสิ้น / Total", val), Paragraph(_baht(charge.amount), total)]],
              colWidths=[None, 50 * mm],
              style=TableStyle([("ALIGN", (1, 0), (1, 0), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])),
        Spacer(1, 8 * mm),
    ]

    if p:
        pay = [
            ["ช่องทาง / Method", "PromptPay"],
            ["ธนาคารต้นทาง / Bank", p.sender_bank or "-"],
            ["เลขอ้างอิงธุรกรรม / Txn ref", p.trans_ref or "-"],
            ["เวลาโอน / Transferred", _fmt(p.transferred_at)],
            ["ตรวจสอบโดย / Verified by", p.provider],
        ]
        pay_tbl = Table([[Paragraph(k, label), Paragraph(str(v), val)] for k, v in pay], colWidths=[55 * mm, None])
        pay_tbl.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3)]))
        elems += [Paragraph("รายละเอียดการชำระเงิน / Payment details", sub), Spacer(1, 2 * mm), pay_tbl]

    elems += [Spacer(1, 12 * mm), Paragraph("ออกโดยระบบ PanPay · เอกสารนี้สร้างอัตโนมัติ", label)]

    doc.build(elems)
    return buf.getvalue()
