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

class InvoiceStatus(str, Enum):
    draft = "Draft"
    issued = "Issued"
    partially_paid = "PartiallyPaid"
    paid = "Paid"
    cancelled = "Cancelled"

class PaymentMethod(str, Enum):
    cash = "Cash"
    card = "Card"
    click = "Click"
    payme = "Payme"


class PaymentStatus(str, Enum):
    pending = "Pending"
    paid = "Paid"
    failed = "Failed"
    cancelled = "Cancelled"


class ReceiptStatus(str, Enum):
    pending = "Pending"
    issued = "Issued"
    failed = "Failed"

class CommissionKind(str, Enum):
    percent = "Percent"
    fixed = "Fixed"


class CommissionBase(str, Enum):
    with_vat = "WithVat"  # to'langan summa (QQS bilan)
    net_of_vat = "NetOfVat"  # QQS ajratilgan


class CommissionEntryKind(str, Enum):
    accrual = "Accrual"
    reversal = "Reversal"

class CashShiftStatus(str, Enum):
    open = "Open"
    closed = "Closed"

class CashMovementKind(str, Enum):
    withdrawal = "Withdrawal"  # inkassatsiya
    payout = "Payout"  # shifokor foizi naqd to'lovi

class PayoutStatus(str, Enum):
    draft = "Draft"
    approved = "Approved"
    paid = "Paid"


class PayoutMethod(str, Enum):
    cash = "Cash"
    transfer = "Transfer"

class Channel(str, Enum):
    sms = "SMS"
    telegram = "Telegram"


class ConsentStatus(str, Enum):
    granted = "Granted"
    revoked = "Revoked"


class MessageStatus(str, Enum):
    queued = "Queued"
    sent = "Sent"
    failed = "Failed"
    skipped = "Skipped"


class StockKind(str, Enum):
    medicine = "Medicine"
    supply = "Supply"
