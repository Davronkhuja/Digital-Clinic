from datetime import date, time
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import ExceptionKind


def _check_hours(start: time | None, end: time | None, b_start: time | None, b_end: time | None) -> None:
    if start is not None and end is not None and end <= start:
        raise ValueError("Tugash vaqti boshlanishdan keyin bo'lishi kerak")
    if (b_start is None) != (b_end is None):
        raise ValueError("Tanaffusning boshlanishi va tugashi birga ko'rsatiladi")
    if b_start is not None:
        if b_end <= b_start:
            raise ValueError("Tanaffus tugashi boshlanishidan keyin bo'lishi kerak")
        if start is not None and end is not None and not (start <= b_start and b_end <= end):
            raise ValueError("Tanaffus ish soatlari ichida bo'lishi kerak")


class ScheduleDay(BaseModel):
    weekday: int = Field(..., ge=0, le=6, description="0=dushanba ... 6=yakshanba")
    start_time: time = Field(..., examples=["09:00"])
    end_time: time = Field(..., examples=["17:00"])
    break_start: Optional[time] = Field(None, examples=["13:00"])
    break_end: Optional[time] = Field(None, examples=["14:00"])

    @model_validator(mode="after")
    def _valid(self):
        _check_hours(self.start_time, self.end_time, self.break_start, self.break_end)
        return self


class ScheduleTemplate(BaseModel):
    """Haftalik shablon: ro'yxatda yo'q kunlar dam olish kuni. Bo'sh ro'yxat: shablon yo'q (cheklovsiz)."""

    days: List[ScheduleDay]

    @model_validator(mode="after")
    def _unique_days(self):
        if len({d.weekday for d in self.days}) != len(self.days):
            raise ValueError("Hafta kuni takrorlangan")
        return self


class ExceptionIn(BaseModel):
    kind: ExceptionKind
    date_from: date
    date_to: Optional[date] = Field(None, description="Bo'lmasa date_from; ExtraWork uchun bir kun")
    start_time: Optional[time] = Field(None, description="Faqat ExtraWork")
    end_time: Optional[time] = Field(None, description="Faqat ExtraWork")
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    note: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def _valid(self):
        end = self.date_to or self.date_from
        if end < self.date_from:
            raise ValueError("date_to date_from dan oldin bo'lishi mumkin emas")
        if self.kind == ExceptionKind.extra_work:
            if self.start_time is None or self.end_time is None:
                raise ValueError("ExtraWork uchun start_time va end_time kerak")
            if end != self.date_from:
                raise ValueError("ExtraWork bir kunlik bo'lishi kerak")
            _check_hours(self.start_time, self.end_time, self.break_start, self.break_end)
        elif any(v is not None for v in (self.start_time, self.end_time, self.break_start, self.break_end)):
            raise ValueError("Soatlar faqat ExtraWork uchun")
        return self


class ExceptionOut(BaseModel):
    id: str
    kind: ExceptionKind
    date_from: date
    date_to: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    note: Optional[str] = None
    affected_appointments: List[str] = Field(default_factory=list, description="Shu davrga tushgan rejalashtirilgan qabullar (ID)")


class ScheduleOut(BaseModel):
    staff_id: str
    days: List[ScheduleDay]
    exceptions: List[ExceptionOut]


class Slot(BaseModel):
    time: str
    end_time: str


class SlotsOut(BaseModel):
    date: str
    doctor_id: str
    duration_min: int
    room_id: Optional[str] = None
    slots: List[Slot]


