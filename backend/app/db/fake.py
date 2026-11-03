"""Vaqtinchalik xotiradagi ma'lumotlar (PostgreSQL kelguncha)."""
from app.core.security import hash_password, new_id  # noqa: F401
from app.schemas import *  # noqa: F403

fake_users = {
    "admin@clinic.uz": {"id": "1", "name": "Admin User", "email": "admin@clinic.uz",
                         "password_hash": hash_password("password123"), "role": "admin"}
}

fake_patients = [
    Patient(id="1", name="Aziza Karimova", phone="+998 90 123 4567", age=34, gender=GenderEnum.female,
            last_visit="2026-02-20", status=StatusEnum.active, doctor="Dr. Rustamov",
            blood_type="A+", address="Toshkent, Yunusobod", created_at="2025-01-10"),
    Patient(id="2", name="Bobur Aliyev", phone="+998 91 234 5678", age=45, gender=GenderEnum.male,
            last_visit="2026-02-18", status=StatusEnum.active, doctor="Dr. Karimov",
            blood_type="O+", address="Toshkent, Chilonzor", created_at="2025-02-15"),
    Patient(id="3", name="Dilnoza Rahimova", phone="+998 93 345 6789", age=28, gender=GenderEnum.female,
            last_visit="2026-02-15", status=StatusEnum.inactive, doctor="Dr. Yusupov",
            blood_type="B-", address="Samarqand", created_at="2025-03-20"),
    Patient(id="4", name="Eldor Toshmatov", phone="+998 94 456 7890", age=52, gender=GenderEnum.male,
            last_visit="2026-02-22", status=StatusEnum.active, doctor="Dr. Rustamov",
            blood_type="AB+", address="Toshkent, Mirzo Ulugbek", created_at="2025-04-05"),
    Patient(id="5", name="Feruza Umarova", phone="+998 95 567 8901", age=39, gender=GenderEnum.female,
            last_visit="2026-02-21", status=StatusEnum.active, doctor="Dr. Karimov",
            blood_type="A-", address="Andijon", created_at="2025-05-12"),
]

fake_appointments = [
    Appointment(id="1", patient_id="1", patient_name="Aziza Karimova", doctor="Dr. Rustamov",
                date="2026-02-25", time="10:00", type="Konsultatsiya",
                status=AppointmentStatus.scheduled, created_at="2026-02-22"),
    Appointment(id="2", patient_id="2", patient_name="Bobur Aliyev", doctor="Dr. Karimov",
                date="2026-02-25", time="11:30", type="Tekshiruv",
                status=AppointmentStatus.scheduled, created_at="2026-02-22"),
    Appointment(id="3", patient_id="3", patient_name="Dilnoza Rahimova", doctor="Dr. Yusupov",
                date="2026-02-24", time="09:00", type="Jarrohlik",
                status=AppointmentStatus.completed, created_at="2026-02-20"),
]

fake_emr = [
    EMRRecord(id="1", patient_id="1", patient_name="Aziza Karimova", doctor="Dr. Rustamov",
              diagnosis="Gipertenziya 2-darajali", prescription="Amlodipine 5mg",
              visit_date="2026-02-20", created_at="2026-02-20"),
    EMRRecord(id="2", patient_id="2", patient_name="Bobur Aliyev", doctor="Dr. Karimov",
              diagnosis="Qandli diabet 2-turi", prescription="Metformin 500mg",
              visit_date="2026-02-18", created_at="2026-02-18"),
]

fake_transactions = [
    Transaction(id="1", type=TransactionType.income, amount=250000,
                description="Konsultatsiya to'lovi", patient_name="Aziza Karimova",
                category="Consultation", date="2026-02-23", created_at="2026-02-23"),
    Transaction(id="2", type=TransactionType.income, amount=450000,
                description="Jarrohlik xizmati", patient_name="Bobur Aliyev",
                category="Surgery", date="2026-02-22", created_at="2026-02-22"),
    Transaction(id="3", type=TransactionType.expense, amount=1200000,
                description="Tibbiy jihozlar", patient_name=None,
                category="Equipment", date="2026-02-21", created_at="2026-02-21"),
    Transaction(id="4", type=TransactionType.income, amount=180000,
                description="Laboratoriya tahlili", patient_name="Dilnoza Rahimova",
                category="Lab", date="2026-02-20", created_at="2026-02-20"),
]

fake_staff = [
    StaffMember(id="1", name="Dr. Behruz Rustamov", role=StaffRole.doctor, department="Kardiologiya",
                phone="+998 90 111 2233", email="rustamov@clinic.uz", status=StatusEnum.active,
                joined_date="2023-01-15", patients_count=124, schedule="Du-Ju 09:00-17:00"),
    StaffMember(id="2", name="Dr. Zulfiya Karimova", role=StaffRole.doctor, department="Nevrologiya",
                phone="+998 91 222 3344", email="karimova@clinic.uz", status=StatusEnum.active,
                joined_date="2022-06-01", patients_count=98, schedule="Du-Jsh 10:00-18:00"),
    StaffMember(id="3", name="Malika Yusupova", role=StaffRole.nurse, department="Terapiya",
                phone="+998 93 333 4455", email="yusupova@clinic.uz", status=StatusEnum.active,
                joined_date="2024-03-10", patients_count=0, schedule="Du-Ju 08:00-16:00"),
    StaffMember(id="4", name="Jasur Mirzayev", role=StaffRole.receptionist, department="Qabul",
                phone="+998 94 444 5566", email="mirzayev@clinic.uz", status=StatusEnum.active,
                joined_date="2024-01-05", patients_count=0, schedule="Du-Sha 09:00-18:00"),
]

clinic_settings = ClinicSettings(
    clinic_name="Digital Clinic",
    address="Toshkent, Amir Temur ko'chasi 1",
    phone="+998 71 200 0000",
    email="info@digitalclinic.uz",
)
