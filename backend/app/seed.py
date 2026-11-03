"""Boshlang'ich ma'lumotlar: `python -m app.seed` (idempotent).

- Muhim ma'lumotlar (filial, rollar, ruxsatlar, sozlamalar) har doim yetishmasa yaratiladi.
- Demo ma'lumotlar faqat SEED_DEMO=true va baza bo'sh bo'lganda yuklanadi.
"""
import logging
from datetime import UTC, date, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Appointment,
    Branch,
    ClinicSettings,
    Encounter,
    Patient,
    Permission,
    Prescription,
    Role,
    Staff,
    Transaction,
    User,
)
from app.schemas.enums import AppointmentStatus, GenderEnum, StaffRole, StatusEnum, TransactionType

log = logging.getLogger("seed")

DEMO_PASSWORD = "password123"  # faqat demo uchun


def seed_essentials(db: Session) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.is_default.is_(True)))
    if not branch:
        branch = Branch(name="Asosiy filial", address="Toshkent, Amir Temur ko'chasi 1",
                        phone="+998 71 200 0000", is_default=True)
        db.add(branch)
        db.flush()
    if not db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == branch.id)):
        db.add(ClinicSettings(branch_id=branch.id, clinic_name="Digital Clinic", address=branch.address,
                              phone=branch.phone, email="info@digitalclinic.uz"))
    perms = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code, desc in PERMISSIONS.items():
        if code not in perms:
            perms[code] = Permission(code=code, description=desc)
            db.add(perms[code])
    existing_roles = {r.code for r in db.scalars(select(Role)).all()}
    for code, (name, codes) in ROLES.items():
        if code not in existing_roles:  # mavjud rolning ruxsatlariga tegilmaydi (admin sozlagan bo'lishi mumkin)
            db.add(Role(code=code, name=name, is_system=True, permissions=[perms[c] for c in codes]))
    db.flush()
    return branch


def _add_staff(db, branch, role_codes, full_name, role, dept, phone, email, joined, schedule, with_login=True):
    staff = Staff(full_name=full_name, role=role, department=dept, phone=phone, email=email, schedule=schedule,
                  joined_date=joined, branch_id=branch.id)
    db.add(staff)
    db.flush()
    if with_login:
        db.add(User(staff_id=staff.id, role_id=role_codes[ROLE_FOR[role]], email=email,
                    password_hash=DEMO_HASH[0], branch_id=branch.id))
    return staff


ROLE_FOR = {StaffRole.admin: "admin", StaffRole.doctor: "doctor", StaffRole.nurse: "nurse",
            StaffRole.receptionist: "receptionist", StaffRole.cashier: "cashier"}
DEMO_HASH: list[str] = []


def seed_admin_from_env(db: Session, branch: Branch) -> None:
    role = db.scalar(select(Role).where(Role.code == "admin"))
    staff = Staff(full_name="Administrator", role=StaffRole.admin, email=settings.admin_email.lower(),
                  joined_date=date.today(), branch_id=branch.id)
    db.add(staff)
    db.flush()
    db.add(User(staff_id=staff.id, role_id=role.id, email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password), branch_id=branch.id))
    log.info("Birinchi administrator yaratildi: %s", settings.admin_email)


def seed_demo(db: Session, branch: Branch) -> None:
    today = date.today()
    shift = today - date(2026, 2, 25)  # asl demo sanalarini "yaqin" qilib siljitadi
    d = lambda y, m, dd: date(y, m, dd) + shift  # noqa: E731

    DEMO_HASH.append(hash_password(DEMO_PASSWORD))
    roles = {r.code: r.id for r in db.scalars(select(Role)).all()}
    mk = lambda *a, **k: _add_staff(db, branch, roles, *a, **k)  # noqa: E731
    mk("Admin User", StaffRole.admin, "Boshqaruv", "+998 71 200 0001", "admin@clinic.uz", d(2022, 1, 10), "Du-Ju 09:00-18:00")
    rustamov = mk("Dr. Behruz Rustamov", StaffRole.doctor, "Kardiologiya", "+998 90 111 2233", "rustamov@clinic.uz", d(2023, 1, 15), "Du-Ju 09:00-17:00")
    karimova = mk("Dr. Zulfiya Karimova", StaffRole.doctor, "Nevrologiya", "+998 91 222 3344", "karimova@clinic.uz", d(2022, 6, 1), "Du-Jsh 10:00-18:00")
    yusupov = mk("Dr. Akmal Yusupov", StaffRole.doctor, "Dermatologiya", "+998 97 555 6677", "yusupov@clinic.uz", d(2023, 9, 1), "Se-Sha 10:00-18:00")
    mk("Malika Yusupova", StaffRole.nurse, "Terapiya", "+998 93 333 4455", "yusupova@clinic.uz", d(2024, 3, 10), "Du-Ju 08:00-16:00")
    mk("Jasur Mirzayev", StaffRole.receptionist, "Qabul", "+998 94 444 5566", "mirzayev@clinic.uz", d(2024, 1, 5), "Du-Sha 09:00-18:00")
    mk("Dilfuza Akbarova", StaffRole.cashier, "Kassa", "+998 95 666 7788", "akbarova@clinic.uz", d(2024, 5, 20), "Du-Sha 09:00-18:00")

    def patient(name, phone, age, gender, doctor, blood, addr, status, created):
        p = Patient(full_name=name, phone=phone, birth_date=today.replace(year=today.year - age), gender=gender,
                    primary_doctor_id=doctor.id, blood_type=blood, address=addr, status=status,
                    branch_id=branch.id)
        p.created_at = created
        db.add(p)
        return p

    from datetime import datetime
    ts = lambda y, m, dd: datetime(y, m, dd, 9, 0, tzinfo=UTC)  # noqa: E731
    aziza = patient("Aziza Karimova", "+998 90 123 4567", 34, GenderEnum.female, rustamov, "A+", "Toshkent, Yunusobod", StatusEnum.active, ts(2025, 1, 10))
    bobur = patient("Bobur Aliyev", "+998 91 234 5678", 45, GenderEnum.male, karimova, "O+", "Toshkent, Chilonzor", StatusEnum.active, ts(2025, 2, 15))
    dilnoza = patient("Dilnoza Rahimova", "+998 93 345 6789", 28, GenderEnum.female, yusupov, "B-", "Samarqand", StatusEnum.inactive, ts(2025, 3, 20))
    eldor = patient("Eldor Toshmatov", "+998 94 456 7890", 52, GenderEnum.male, rustamov, "AB+", "Toshkent, Mirzo Ulug'bek", StatusEnum.active, ts(2025, 4, 5))
    feruza = patient("Feruza Umarova", "+998 95 567 8901", 39, GenderEnum.female, karimova, "A-", "Andijon", StatusEnum.active, ts(2025, 5, 12))
    db.flush()
    patients = [aziza, bobur, dilnoza, eldor, feruza]
    doctors = [rustamov, karimova, yusupov]

    def appt(p, doc, day, hh, mm, kind, st):
        db.add(Appointment(patient_id=p.id, doctor_id=doc.id, date=day, time=time(hh, mm), type=kind, status=st,
                           branch_id=branch.id))

    S = AppointmentStatus
    appt(aziza, rustamov, d(2026, 2, 25), 10, 0, "Konsultatsiya", S.scheduled)
    appt(bobur, karimova, d(2026, 2, 25), 11, 30, "Tekshiruv", S.scheduled)
    appt(dilnoza, yusupov, d(2026, 2, 24), 9, 0, "Jarrohlik", S.completed)
    # Oxirgi 8 hafta uchun deterministik tarix (dashboard va tahlil uchun)
    kinds = ["Konsultatsiya", "Tekshiruv", "Qayta ko'rik", "Laboratoriya"]
    for i in range(1, 57):
        day = today - timedelta(days=i)
        if day.weekday() == 6:
            continue
        st = [S.completed, S.completed, S.completed, S.cancelled, S.no_show][i % 5]
        appt(patients[i % 5], doctors[i % 3], day, 9 + (i % 8), 30 * (i % 2), kinds[i % 4], st)
    for i in range(1, 8):
        appt(patients[(i + 2) % 5], doctors[(i + 1) % 3], today + timedelta(days=i), 9 + (i % 6), 0, kinds[i % 4], S.scheduled)

    def encounter(p, doc, day, icd, diagnosis, rx, notes):
        e = Encounter(patient_id=p.id, doctor_id=doc.id, visit_date=day, icd_code=icd, diagnosis=diagnosis,
                      notes=notes, branch_id=branch.id)
        db.add(e)
        db.flush()
        db.add(Prescription(encounter_id=e.id, patient_id=p.id, medication=rx, branch_id=branch.id))

    encounter(aziza, rustamov, d(2026, 2, 20), "I10", "Gipertenziya 2-darajali", "Amlodipine 5mg", "Tuz iste'molini kamaytirish")
    encounter(bobur, karimova, d(2026, 2, 18), "E11", "Qandli diabet 2-turi", "Metformin 500mg", "Qon glyukozasini nazorat qilish")

    def tx(kind, amount, desc, cat, day, p=None):
        db.add(Transaction(type=kind, amount=Decimal(amount), description=desc, category=cat, date=day,
                           patient_id=p.id if p else None, branch_id=branch.id))

    T = TransactionType
    tx(T.income, 250000, "Konsultatsiya to'lovi", "Consultation", d(2026, 2, 23), aziza)
    tx(T.income, 450000, "Jarrohlik xizmati", "Surgery", d(2026, 2, 22), bobur)
    tx(T.expense, 1200000, "Tibbiy jihozlar", "Equipment", d(2026, 2, 21))
    tx(T.income, 180000, "Laboratoriya tahlili", "Lab", d(2026, 2, 20), dilnoza)
    # Oxirgi 6 oy: har oyda daromad va xarajat (grafiklar uchun)
    for m in range(1, 7):
        base = today.replace(day=15) - timedelta(days=30 * m)
        for j, (cat, amt) in enumerate([("Consultation", 6_000_000), ("Lab", 2_500_000), ("Surgery", 9_000_000)]):
            tx(T.income, amt + 350_000 * ((m * 3 + j) % 5), f"{cat} (oylik jami)", cat, base - timedelta(days=j), patients[(m + j) % 5])
        tx(T.expense, 7_000_000 + 400_000 * (m % 4), "Oylik xarajatlar", "Operations", base)
    db.flush()


class SeedError(SystemExit):
    """Boshlang'ich sozlash xatosi: konteyner ishga tushmaydi."""


MIN_ADMIN_PASSWORD_LENGTH = 10


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        branch = seed_essentials(db)
        users = db.scalar(select(func.count()).select_from(User))
        patients = db.scalar(select(func.count()).select_from(Patient))
        if settings.seed_demo and not (users or patients):
            seed_demo(db, branch)
            log.info("Demo ma'lumotlar yuklandi")
        elif not users:
            # Demo yo'q va bazada foydalanuvchi yo'q: birinchi administrator env'dan majburiy
            if not (settings.admin_email and settings.admin_password):
                raise SeedError(
                    "SEED_DEMO=false va bazada foydalanuvchi yo'q: ADMIN_EMAIL va ADMIN_PASSWORD berilishi shart."
                )
            if len(settings.admin_password) < MIN_ADMIN_PASSWORD_LENGTH:
                raise SeedError(f"ADMIN_PASSWORD kamida {MIN_ADMIN_PASSWORD_LENGTH} belgi bo'lishi kerak.")
            seed_admin_from_env(db, branch)
        db.commit()


if __name__ == "__main__":
    main()
