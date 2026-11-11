from enum import Enum


class GenderEnum(str, Enum):
    male = "male"
    female = "female"
    other = "other"

class StatusEnum(str, Enum):
    active = "Active"
    inactive = "Inactive"

class AppointmentStatus(str, Enum):
    scheduled = "Scheduled"
    completed = "Completed"
    cancelled = "Cancelled"
    no_show = "No Show"

class TransactionType(str, Enum):
    income = "income"
    expense = "expense"

class StaffRole(str, Enum):
    doctor = "Doctor"
    nurse = "Nurse"
    receptionist = "Receptionist"
    admin = "Admin"
    lab_tech = "Lab Technician"
    cashier = "Cashier"

class ExceptionKind(str, Enum):
    day_off = "DayOff"
    vacation = "Vacation"
    sick = "Sick"
    extra_work = "ExtraWork"

class WaitlistStatus(str, Enum):
    waiting = "Waiting"
    booked = "Booked"
    cancelled = "Cancelled"

class RouteEnum(str, Enum):
    oral = "Oral"
    intravenous = "Intravenous"
    intramuscular = "Intramuscular"
    subcutaneous = "Subcutaneous"
    topical = "Topical"
    inhalation = "Inhalation"
    sublingual = "Sublingual"
    rectal = "Rectal"
    ophthalmic = "Ophthalmic"
    nasal = "Nasal"
    otic = "Otic"
    vaginal = "Vaginal"

class LabOrderStatus(str, Enum):
    ordered = "Ordered"
    completed = "Completed"
    cancelled = "Cancelled"


class LabFlag(str, Enum):
    low = "Low"
    normal = "Normal"
    high = "High"
