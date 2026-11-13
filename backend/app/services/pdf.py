# ruff: noqa: E501
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
    if any(i.get("ref_verified") is False for i in order["items"]):
        story += [_p("Diqqat: ishlatilgan me'yorlar namuna (tasdiqlanmagan); laboratoriya o'z me'yorini tasdiqlashi kerak.", abnormal),
                  Spacer(1, 2 * mm)]
    story.append(_p("Me'yor oralig'i bemorning jinsi va yoshiga ko'ra tanlangan; \"—\": mos me'yor yo'q. "
                    "Natijalarni shifokor baholaydi.", small))
    doc.build(story)
    return buffer.getvalue()


def encounter_card_pdf(card: dict, clinic: dict) -> bytes:
    """Ko'rik kartasi chop etish uchun (DMED maydonlari tartibida): bemor, murojaat, bo'limlar, MKB-10, retsept, laboratoriya."""
    regular, bold = _fonts()
    base = ParagraphStyle("base", fontName=regular, fontSize=9.5, leading=12.5)
    strong = ParagraphStyle("strong", parent=base, fontName=bold)
    title = ParagraphStyle("title", parent=base, fontName=bold, fontSize=15, leading=19)
    label = ParagraphStyle("label", parent=base, fontSize=8.5, textColor=colors.HexColor("#64748b"))
    abnormal = ParagraphStyle("abnormal", parent=strong, textColor=colors.HexColor("#b91c1c"))

    buffer = io.BytesIO()
    patient_name = next((f["value"] for f in card["patient"] if f["key"] == "full_name"), "")
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Ko'rik kartasi: {patient_name}", author=clinic.get("name") or "Digital Clinic")

    def pairs(fields: list[dict]) -> Table:
        table = Table([[_p(f["label"], label), _p(f["value"], base)] for f in fields], colWidths=[40 * mm, 130 * mm])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                   ("TOPPADDING", (0, 0), (-1, -1), 2)]))
        return table

    def heading(text: str) -> list:
        return [Spacer(1, 4 * mm), _p(text, strong), Spacer(1, 1.5 * mm)]

    story = [_p(clinic.get("name") or "Digital Clinic", title),
             _p(" · ".join(x for x in (clinic.get("address"), clinic.get("phone")) if x), label), Spacer(1, 4 * mm),
             _p("Ko'rik kartasi", ParagraphStyle("h", parent=title, fontSize=13))]
    story += heading("Bemor") + [pairs(card["patient"])]
    story += heading("Murojaat") + [pairs(card["visit"])]
    for f in card["sections"]:
        story += [Spacer(1, 3 * mm), _p(f["label"], label), _p(f["value"], base)]
        if f["key"] == "diagnosis" and card.get("icd_code"):
            story.append(_p(f"MKB-10: {card['icd_code']}" + (f" — {card['icd_name']}" if card.get("icd_name") else ""), strong))
    if card["prescriptions"]:
        story += heading("Retsept (INN)")
        rows = [[_p(h, label) for h in ("Dori (INN)", "Doza", "Usul", "Chastota", "Muddat")]]
        for p in card["prescriptions"]:
            rows.append([_p(p["inn"], strong), _p(p["dose"], base), _p(p["route"], base), _p(p["frequency"], base),
                         _p(f"{p['duration_days']} kun" if p["duration_days"] else None, base)])
            if p.get("instructions"):
                rows.append([_p(p["instructions"], label), "", "", "", ""])
        t = Table(rows, colWidths=[52 * mm, 28 * mm, 30 * mm, 36 * mm, 24 * mm], repeatRows=1)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    if card["lab_results"]:
        story += heading("Laboratoriya natijalari")
        rows = [[_p(h, label) for h in ("Tahlil", "Natija", "Birlik", "Me'yor")]]
        for i in card["lab_results"]:
            out = i["flag"] in ("Low", "High")
            rows.append([_p(i["name"], base), _p(f"{i['value']:g}", abnormal if out else strong), _p(i["unit"], base),
                         _p(i["reference"] or "—", base)])
        t = Table(rows, colWidths=[70 * mm, 30 * mm, 30 * mm, 40 * mm], repeatRows=1)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1"))]))
        story.append(t)
    story += [Spacer(1, 8 * mm), _p("DMED ga qo'lda kiritish uchun nusxa. " + (
        f"DMED ga ko'chirildi: {card['dmed_copied_at'][:10]}" if card.get("dmed_copied_at") else "DMED ga ko'chirilmagan."), label)]
    doc.build(story)
    return buffer.getvalue()


def z_report_pdf(rep: dict, clinic: dict) -> bytes:
    """Z-hisobot (yopilgan smena) yoki X-hisobot (ochiq): to'lov usullari bo'yicha, kutilgan va sanalgan naqd, farq."""
    regular, bold = _fonts()
    base = ParagraphStyle("base", fontName=regular, fontSize=9.5, leading=12.5)
    strong = ParagraphStyle("strong", parent=base, fontName=bold)
    title = ParagraphStyle("title", parent=base, fontName=bold, fontSize=15, leading=19)
    label = ParagraphStyle("label", parent=base, fontSize=8.5, textColor=colors.HexColor("#64748b"))
    bad = ParagraphStyle("bad", parent=strong, textColor=colors.HexColor("#b91c1c"))
    money = lambda v: f"{v:,.2f}".replace(",", " ")  # noqa: E731

    buffer = io.BytesIO()
    kind = "Z-hisobot" if rep.get("z_number") else "X-hisobot (smena ochiq)"
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{kind} {rep.get('z_number') or ''}", author=clinic.get("name") or "Digital Clinic")
    story = [_p(clinic.get("name") or "Digital Clinic", title), _p(" · ".join(x for x in (clinic.get("address"), clinic.get("phone")) if x), label),
             Spacer(1, 4 * mm), _p(f"{kind} {rep.get('z_number') or ''}".strip(), ParagraphStyle("h", parent=title, fontSize=13)), Spacer(1, 3 * mm)]
    info = [[_p("Kassir:", label), _p(rep.get("cashier"), base)], [_p("Ochildi:", label), _p((rep["opened_at"] or "")[:19].replace("T", " "), base)],
            [_p("Yopildi:", label), _p((rep.get("closed_at") or "—")[:19].replace("T", " "), base)]]
    t = Table(info, colWidths=[30 * mm, 140 * mm])
    t.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [t, Spacer(1, 4 * mm)]
    rows = [[_p(h, label) for h in ("Usul", "To'lovlar", "Summa", "Qaytarish", "Qaytarilgan", "Sof")]]
    for name, key in (("Naqd", "cash"), ("Karta", "card")):
        m = rep[key]
        rows.append([_p(name, strong), _p(str(m["payments_count"]), base), _p(money(m["payments_total"]), base), _p(str(m["refunds_count"]), base),
                     _p(money(m["refunds_total"]), base), _p(money(m["net"]), strong)])
    t = Table(rows, colWidths=[28 * mm, 25 * mm, 36 * mm, 25 * mm, 32 * mm, 32 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1"))]))
    story += [t, Spacer(1, 4 * mm)]
    for name, m in rep["online"].items():
        story.append(_p(f"Onlayn {name.capitalize()} (kassaga kirmaydi): {m['payments_count']} ta, {money(m['payments_total'])}", base))
    story += [Spacer(1, 2 * mm), _p(f"Inkassatsiya: {rep['withdrawals']['count']} ta, {money(rep['withdrawals']['total'])}", base),
              _p(f"Foiz to'lovlari (naqd): {rep['payouts']['count']} ta, {money(rep['payouts']['total'])}", base)]
    story += [Spacer(1, 3 * mm), _p(f"Sotuv jami: {money(rep['sales_total'])}   Qaytarish: {money(rep['refunds_total'])}   Sof: {money(rep['net_total'])}", strong),
              Spacer(1, 4 * mm), _p(f"Boshlang'ich naqd: {money(rep['opening_cash'])}", base),
              _p(f"Kutilgan naqd: {money(rep['expected_cash'])}", strong)]
    if rep.get("counted_cash") is not None:
        diff = rep["difference"]
        story += [_p(f"Sanalgan naqd: {money(rep['counted_cash'])}", base),
                  _p(f"Farq: {money(diff)} " + ("(kamomad)" if diff < 0 else "(ortiqcha)" if diff > 0 else "(mos)"), bad if diff else strong)]
    if rep.get("receipts_missing"):
        story += [Spacer(1, 3 * mm), _p(f"Diqqat: {rep['receipts_missing']} ta to'lovning fiskal cheki berilmagan.", bad)]
    doc.build(story)
    return buffer.getvalue()
