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
