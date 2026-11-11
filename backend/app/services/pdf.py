"""PDF hisobotlar (reportlab). Unicode uchun DejaVu shrifti (Dockerfile); topilmasa Helvetica (lotin belgilar)."""
import io
from functools import lru_cache
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu")
FLAG_UZ = {"Low": "Past", "Normal": "Me'yorda", "High": "Yuqori"}
STATUS_UZ = {"Ordered": "Kutilmoqda", "Completed": "Yakunlangan", "Cancelled": "Bekor qilingan"}


@lru_cache
def _fonts() -> tuple[str, str]:
    """(oddiy, qalin) shrift nomlari."""
    for folder in FONT_DIRS:
        regular, bold = Path(folder) / "DejaVuSans.ttf", Path(folder) / "DejaVuSans-Bold.ttf"
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
            return "DejaVu", "DejaVu-Bold"
    return "Helvetica", "Helvetica-Bold"


def _p(text: str | None, style: ParagraphStyle) -> Paragraph:
    safe = (text or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def lab_order_pdf(order: dict, patient: dict, clinic: dict) -> bytes:
    """Laboratoriya natijalari: bemor, shifokor, jadval (natija, birlik, me'yor, belgi); me'yordan tashqari qalin va qizil."""
    regular, bold = _fonts()
    base = ParagraphStyle("base", fontName=regular, fontSize=9.5, leading=12)
    strong = ParagraphStyle("strong", parent=base, fontName=bold)
    abnormal = ParagraphStyle("abnormal", parent=strong, textColor=colors.HexColor("#b91c1c"))
    title = ParagraphStyle("title", parent=base, fontName=bold, fontSize=15, leading=19)
    small = ParagraphStyle("small", parent=base, fontSize=8, textColor=colors.HexColor("#64748b"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Laboratoriya natijalari: {patient['name']}", author=clinic.get("name") or "Digital Clinic")
    story = [
        _p(clinic.get("name") or "Digital Clinic", title),
        _p(" · ".join(x for x in (clinic.get("address"), clinic.get("phone")) if x), small),
        Spacer(1, 6 * mm),
        _p("Laboratoriya natijalari", ParagraphStyle("h", parent=title, fontSize=13)),
        Spacer(1, 3 * mm),
    ]
    info = [
        [_p("Bemor:", small), _p(patient["name"], strong), _p("Tug'ilgan sana:", small), _p(patient.get("birth_date"), base)],
        [_p("Jinsi:", small), _p({"male": "Erkak", "female": "Ayol"}.get(patient.get("gender"), "Boshqa"), base),
         _p("Shifokor:", small), _p(order["doctor"], base)],
        [_p("Buyurtma sanasi:", small), _p((order["created_at"] or "")[:10], base), _p("Holati:", small),
         _p(STATUS_UZ.get(order["status"], order["status"]), base)],
    ]
    info_table = Table(info, colWidths=[30 * mm, 55 * mm, 32 * mm, 55 * mm])
    info_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [info_table, Spacer(1, 5 * mm)]

    rows = [[_p(h, strong) for h in ("Tahlil", "Natija", "Birlik", "Me'yor", "Belgi")]]
    for item in order["items"]:
        out = item["flag"] in ("Low", "High")
        value = "—" if item["value"] is None else f"{item['value']:g}"
        rows.append([
            _p(item["name"], base), _p(value, abnormal if out else strong), _p(item["unit"], base),
            _p(item.get("reference") or "—", base), _p(FLAG_UZ.get(item["flag"], "—") if item["value"] is not None else "—",
                                                       abnormal if out else base),
        ])
    table = Table(rows, colWidths=[62 * mm, 25 * mm, 25 * mm, 32 * mm, 28 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [table, Spacer(1, 6 * mm)]
    if order.get("notes"):
        story += [_p(f"Izoh: {order['notes']}", base), Spacer(1, 3 * mm)]
    story.append(_p("Me'yor oralig'i bemorning jinsi va yoshiga ko'ra tanlangan; \"—\": mos me'yor yo'q. "
                    "Natijalarni shifokor baholaydi.", small))
    doc.build(story)
    return buffer.getvalue()
