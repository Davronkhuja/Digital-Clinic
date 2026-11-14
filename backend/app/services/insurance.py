# ruff: noqa: E501
"""Sug'urta mantiqi: polis/shartnoma amal qilishi, kafolat xati holati va ishlatilgan summa."""
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GuaranteeLetter, InsuranceContract, Insurer, InsurerPayment, PatientPolicy
from app.services.money import q2
from app.services.periods import CLINIC_TZ, clinic_today

ZERO = Decimal("0.00")


def policy_valid(policy: PatientPolicy, contract: InsuranceContract, on: date | None = None) -> bool:
    on = on or clinic_today()
    return (policy.is_active and policy.valid_from <= on and (policy.valid_to is None or policy.valid_to >= on)
            and contract.is_active and contract.valid_from <= on and (contract.valid_to is None or contract.valid_to >= on))


def letter_used(db: Session, letter_id: uuid.UUID) -> Decimal:
    """Kafolat xati bo'yicha ishlatilgan sug'urta ulushi (shu xatga bog'langan, bekor qilinmagan hisob-fakturalar)."""
    from sqlalchemy import func

    from app.models import Invoice
    from app.schemas.enums import InvoiceStatus
    if not hasattr(Invoice, "guarantee_letter_id"):          # hisob-faktura bo'linishi (keyingi versiya) qo'shilguncha ishlatilgan summa 0
        return ZERO
    total = db.scalar(select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
        Invoice.guarantee_letter_id == letter_id, Invoice.status != InvoiceStatus.cancelled))
    return Decimal(total)


def letter_state(letter: GuaranteeLetter, used: Decimal, on: date | None = None) -> str:
    on = on or clinic_today()
    if letter.status == "Cancelled":
        return "Cancelled"
    if (letter.valid_to and letter.valid_to < on) or (letter.valid_from and letter.valid_from > on):
        return "Expired"
    return "Exhausted" if used >= letter.amount_limit else "Active"


@dataclass
class Context:
    policy: PatientPolicy
    contract: InsuranceContract
    letter: GuaranteeLetter | None = None


def load_context(db: Session, patient_id: uuid.UUID, policy_id: uuid.UUID | None, letter_id: uuid.UUID | None,
                 exclude_invoice_id: uuid.UUID | None = None) -> Context | None:
    """Hisob-faktura uchun sug'urta konteksti: polis bemorniki va amal qilayotgan bo'lishi, kafolat xati shu polisniki va faol bo'lishi,
    shartnoma talab qilsa kafolat xati majburiy. Aks holda 422."""
    if not policy_id:
        if letter_id:
            raise HTTPException(422, "Kafolat xati polissiz berilmaydi")
        return None
    policy = db.get(PatientPolicy, policy_id)
    if not policy or policy.patient_id != patient_id:
        raise HTTPException(422, "Polis topilmadi yoki boshqa bemorga tegishli")
    contract = db.get(InsuranceContract, policy.contract_id)
    if not policy_valid(policy, contract):
        raise HTTPException(422, "Polis yoki shartnoma amal qilmayapti (muddat yoki faollik)")
    letter = None
    if letter_id:
        letter = db.get(GuaranteeLetter, letter_id)
        if not letter or letter.policy_id != policy.id:
            raise HTTPException(422, "Kafolat xati topilmadi yoki boshqa polisga tegishli")
        used = letter_used(db, letter.id)
        if exclude_invoice_id:                       # qoralamaning o'z ulushi limitni tugatgan deb hisoblanmasin
            from sqlalchemy import func

            from app.models import Invoice
            used -= Decimal(db.scalar(select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
                Invoice.id == exclude_invoice_id, Invoice.guarantee_letter_id == letter.id)))
        state = letter_state(letter, used)
        if state != "Active":
            raise HTTPException(422, f"Kafolat xati faol emas ({state})")
    if contract.requires_guarantee and not letter:
        raise HTTPException(422, "Bu shartnoma bo'yicha kafolat xati talab qilinadi")
    return Context(policy, contract, letter)


def _scale(shares: list[Decimal], cap: Decimal) -> list[Decimal]:
    """Sug'urta ulushlarini umumiy `cap` ga proporsional kamaytiradi (yaxlitlash qoldig'i ulushi bor qatorlarga)."""
    total = sum(shares, ZERO)
    if total <= cap:
        return shares
    out = [q2(s * cap / total) for s in shares]
    left = cap - sum(out, ZERO)
    for i, s in enumerate(shares):
        if left <= 0:
            break
        extra = min(left, s - out[i])
        out[i] += extra
        left -= extra
    return out


def split(db: Session, ctx: Context, computed, exclude_invoice_id: uuid.UUID | None = None) -> Decimal:
    """Har qatorning sug'urta ulushini hisoblaydi (`insurer_amount`) va umumiy sug'urta ulushini qaytaradi.
    Qoplash: shartnomadagi xizmat foizi (yoki `coverage_all`: standart foiz), kafolat xati xizmatlar ro'yxati bilan cheklasa shu xizmatlar.
    Limitlar: bitta hisob-faktura, bemor uchun kalendar yil (shu shartnoma bo'yicha oldingi hisob-fakturalar), kafolat xati qoldig'i."""
    from sqlalchemy import extract, func

    from app.models import GuaranteeLetterService, InsuranceContractService, Invoice
    from app.schemas.enums import InvoiceStatus
    c = ctx.contract
    coverage = {r.service_id: r.coverage_percent for r in db.scalars(select(InsuranceContractService).where(InsuranceContractService.contract_id == c.id))}
    allowed = None
    if ctx.letter:
        allowed = set(db.scalars(select(GuaranteeLetterService.service_id).where(GuaranteeLetterService.letter_id == ctx.letter.id))) or None
    shares = []
    for ln in computed.lines:
        pct = coverage.get(ln.service.id, c.default_coverage_percent if c.coverage_all else None)
        covered = pct is not None and (allowed is None or ln.service.id in allowed)
        shares.append(q2(ln.net_total * pct / 100) if covered else ZERO)
    caps = []
    if c.per_visit_limit is not None:
        caps.append(c.per_visit_limit)
    if c.annual_limit is not None:
        year = clinic_today().year
        policies = select(PatientPolicy.id).where(PatientPolicy.patient_id == ctx.policy.patient_id, PatientPolicy.contract_id == c.id)
        stmt = select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
            Invoice.policy_id.in_(policies), Invoice.status != InvoiceStatus.cancelled, extract("year", Invoice.created_at) == year)
        if exclude_invoice_id:
            stmt = stmt.where(Invoice.id != exclude_invoice_id)
        caps.append(max(c.annual_limit - Decimal(db.scalar(stmt)), ZERO))
    if ctx.letter:
        used = letter_used(db, ctx.letter.id)
        if exclude_invoice_id:
            used -= Decimal(db.scalar(select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
                Invoice.id == exclude_invoice_id, Invoice.guarantee_letter_id == ctx.letter.id, Invoice.status != InvoiceStatus.cancelled)))
        caps.append(max(ctx.letter.amount_limit - used, ZERO))
    if caps:
        shares = _scale(shares, min(caps))
    for ln, share in zip(computed.lines, shares, strict=True):
        ln.insurer_amount = share
    return sum(shares, ZERO)


def resplit_invoice(db: Session, inv) -> None:
    """Qoralama chiqarilganda: polis, kafolat xati va limitlar qayta tekshiriladi, sug'urta ulushi qayta hisoblanadi."""
    from types import SimpleNamespace

    from app.models import InvoiceLine
    ctx = load_context(db, inv.patient_id, inv.policy_id, inv.guarantee_letter_id, exclude_invoice_id=inv.id)
    lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)))
    proxy = SimpleNamespace(lines=[SimpleNamespace(service=SimpleNamespace(id=ln.service_id), net_total=ln.net_total, insurer_amount=ZERO) for ln in lines])
    inv.insurer_total = split(db, ctx, proxy, exclude_invoice_id=inv.id)
    for ln, p in zip(lines, proxy.lines, strict=True):
        ln.insurer_amount = p.insurer_amount


# ---------- Qarzdorlik va reyestr ----------

def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def receivables(db: Session, insurer_id: uuid.UUID, today: date | None = None) -> dict:
    """Kompaniya qarzi: bekor qilinmagan, chiqarilgan hisob-fakturalardagi sug'urta ulushi (hamma filial) minus kompaniya to'lovlari.
    To'lovlar eng eski hisob-fakturalarga (FIFO) taqsimlanadi. To'lov muddati = hisob-faktura oyi oxiri + kompaniyaning to'lov kunlari."""
    from sqlalchemy import func

    from app.models import Invoice, Patient
    from app.schemas.enums import InvoiceStatus
    today = today or clinic_today()
    insurer = db.get(Insurer, insurer_id)
    invoices = db.execute(select(Invoice, Patient.full_name, PatientPolicy.number).join(Patient, Invoice.patient_id == Patient.id)
                          .outerjoin(PatientPolicy, Invoice.policy_id == PatientPolicy.id)
                          .where(Invoice.insurer_id == insurer_id, Invoice.insurer_total > 0,
                                 Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partially_paid, InvoiceStatus.paid]))
                          .order_by(Invoice.issued_at, Invoice.number)).all()
    paid_total = Decimal(db.scalar(select(func.coalesce(func.sum(InsurerPayment.amount), 0)).where(
        InsurerPayment.insurer_id == insurer_id, InsurerPayment.reversed_at.is_(None))))
    left, open_rows, charged = paid_total, [], ZERO
    buckets = {"current": ZERO, "d1_30": ZERO, "d31_60": ZERO, "d61_90": ZERO, "d90_plus": ZERO}
    for inv, patient, policy_no in invoices:
        charged += inv.insurer_total
        allocated = min(left, inv.insurer_total)
        left -= allocated
        outstanding = inv.insurer_total - allocated
        if outstanding <= 0:
            continue
        issued = inv.issued_at.astimezone(CLINIC_TZ).date()
        due = _month_end(issued) + timedelta(days=insurer.payment_days)
        late = (today - due).days
        key = "current" if late <= 0 else "d1_30" if late <= 30 else "d31_60" if late <= 60 else "d61_90" if late <= 90 else "d90_plus"
        buckets[key] += outstanding
        open_rows.append({"invoice_id": str(inv.id), "number": inv.number, "date": issued, "patient": patient, "policy": policy_no, "amount": inv.insurer_total,
                          "paid": allocated, "outstanding": outstanding, "due_date": due, "days_overdue": max(late, 0)})
    return {"insurer_id": str(insurer_id), "insurer": insurer.name, "payment_days": insurer.payment_days, "charged": charged, "paid": paid_total,
            "balance": charged - paid_total, "overpaid": max(paid_total - charged, ZERO), "overdue": sum((v for k, v in buckets.items() if k != "current"), ZERO),
            "aging": buckets, "open_invoices": open_rows}


def registry_rows(db: Session, insurer_id: uuid.UUID, year: int, month: int, branch_id: uuid.UUID | None) -> list[dict]:
    """Oylik reyestr qatorlari: shu oyda chiqarilgan hisob-fakturalarning sug'urta ulushi bor qatorlari."""
    from sqlalchemy import Date, cast, func

    from app.models import Branch, Invoice, InvoiceLine, Patient
    from app.schemas.enums import InvoiceStatus
    day = cast(func.timezone(str(CLINIC_TZ), Invoice.issued_at), Date)
    stmt = (select(InvoiceLine, Invoice, day, Patient.full_name, PatientPolicy.number, GuaranteeLetter.number, InsuranceContract.number, Branch.name)
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id).join(Patient, Invoice.patient_id == Patient.id)
            .outerjoin(PatientPolicy, Invoice.policy_id == PatientPolicy.id).outerjoin(InsuranceContract, PatientPolicy.contract_id == InsuranceContract.id)
            .outerjoin(GuaranteeLetter, Invoice.guarantee_letter_id == GuaranteeLetter.id).join(Branch, Invoice.branch_id == Branch.id)
            .where(Invoice.insurer_id == insurer_id, InvoiceLine.insurer_amount > 0,
                   Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partially_paid, InvoiceStatus.paid]),
                   func.extract("year", day) == year, func.extract("month", day) == month)
            .order_by(Invoice.issued_at, Invoice.number, InvoiceLine.position))
    if branch_id:
        stmt = stmt.where(Invoice.branch_id == branch_id)
    return [{"date": d, "invoice": inv.number, "patient": patient, "policy": policy, "letter": letter, "contract": contract, "service": ln.name, "qty": ln.quantity,
             "line_total": ln.net_total, "insurer_amount": ln.insurer_amount, "patient_amount": ln.net_total - ln.insurer_amount, "branch": branch}
            for ln, inv, d, patient, policy, letter, contract, branch in db.execute(stmt).all()]


def registry_xlsx(db: Session, head: dict, rows: list[dict], summary: dict, branch_id: uuid.UUID | None) -> bytes:
    """Reyestr Excel fayli: sarlavha (kompaniya, oy, raqam), qatorlar, jami, imzo joyi; ikkinchi varaq: xizmatlar bo'yicha jami."""
    import io

    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    from app.models import ClinicSettings
    clinic = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == branch_id)) if branch_id else db.scalar(select(ClinicSettings).limit(1))
    wb = Workbook()
    ws = wb.active
    ws.title = "Reyestr"
    ws.append([f"Xizmatlar reyestri № {head['number']}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Klinika: {clinic.clinic_name if clinic else ''}"])
    ws.append([f"Sug'urta kompaniyasi: {head['insurer']}" + (f" (STIR {head['tin']})" if head["tin"] else "")])
    ws.append([f"Davr: {head['month']} · hisob-fakturalar: {head['invoices']} · to'lov muddati: oy oxiridan {head['payment_days']} kun"])
    ws.append([])
    cols = ["Sana", "Hisob-faktura", "Bemor", "Polis", "Kafolat xati", "Shartnoma", "Xizmat", "Soni", "Summa", "Sug'urta ulushi", "Bemor ulushi", "Filial"]
    ws.append(cols)
    for c in ws[6]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([r["date"], r["invoice"], r["patient"], r["policy"], r["letter"], r["contract"], r["service"], r["qty"], float(r["line_total"]), float(r["insurer_amount"]),
                   float(r["patient_amount"]), r["branch"]])
    ws.append(["Jami", None, None, None, None, None, None, sum(r["qty"] for r in rows), float(sum((r["line_total"] for r in rows), Decimal(0))),
               float(head["insurer_total"]), float(head["patient_total"])])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    ws.append([])
    ws.append(["Kompaniyaga to'lash: ", float(head["insurer_total"]), "UZS"])
    ws.append(["Klinika vakili: ________________", None, None, None, "Kompaniya vakili: ________________"])
    for i in range(7, ws.max_row):
        ws.cell(row=i, column=1).number_format = "DD.MM.YYYY"
    for col in (9, 10, 11):
        for i in range(7, ws.max_row + 1):
            ws.cell(row=i, column=col).number_format = "#,##0.00"
    for i, w in enumerate([12, 14, 26, 14, 14, 14, 30, 7, 14, 16, 14, 18], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A7"
    s2 = wb.create_sheet("Xizmatlar bo'yicha")
    s2.append(["Xizmat", "Soni", "Summa", "Sug'urta ulushi"])
    for c in s2[1]:
        c.font = Font(bold=True)
    for name, (n, total, share) in sorted(summary.items()):
        s2.append([name, n, float(total), float(share)])
    for i, w in enumerate([34, 8, 16, 18], 1):
        s2.column_dimensions[get_column_letter(i)].width = w
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
