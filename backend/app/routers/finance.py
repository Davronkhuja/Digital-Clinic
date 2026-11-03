from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Transaction
from app.schemas import Transaction as TransactionOut
from app.schemas import TransactionCreate, TransactionType
from app.services import audit, queries
from app.services.lookup import get_patient_or_404, resolve_patient_by_name
from app.services.periods import window

router = APIRouter()


@router.get("/finance/transactions", tags=["💰 Finance"], response_model=List[TransactionOut],
            summary="Moliyaviy tranzaksiyalar")
def get_transactions(request: Request, type: Optional[TransactionType] = Query(None), category: Optional[str] = Query(None),
                     db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:read"))):
    result = queries.list_transactions(db, type, category)
    audit.record_read(db, user, request, "transaction", details={"count": len(result)})
    return result


@router.post("/finance/transactions", tags=["💰 Finance"], response_model=TransactionOut, status_code=201,
             summary="Yangi tranzaksiya qo'shish")
def create_transaction(data: TransactionCreate, request: Request, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("finance:write"))):
    if data.patient_id:
        patient = get_patient_or_404(db, data.patient_id)
    else:
        patient = resolve_patient_by_name(db, data.patient_name)
        if data.patient_name and data.patient_name.strip() and not patient:
            raise HTTPException(422, f"'{data.patient_name}' nomli bemor topilmadi")
    try:
        tx_date = date.fromisoformat(data.date)
    except ValueError:
        raise HTTPException(422, "date noto'g'ri")
    tx = Transaction(type=data.type, amount=data.amount, description=data.description, category=data.category,
                     date=tx_date, patient_id=patient.id if patient else None,
                     branch_id=user.branch_id, created_by=user.id)
    db.add(tx)
    db.flush()
    audit.record(db, user, request, "create", "transaction", tx.id, {"type": data.type.value, "amount": str(data.amount)})
    db.commit()
    return queries.ser.transaction_out(tx, patient.full_name if patient else None)


@router.get("/finance/summary", tags=["💰 Finance"], summary="Moliyaviy xulosa",
            description="Tanlangan davr uchun daromad, xarajat va foyda (bazadan hisoblanadi).")
def get_finance_summary(period: str = Query("month", pattern="^(week|month|year|all)$"),
                        db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:read"))):
    start, _ = window(period)
    stmt = select(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0), func.count()).where(
        Transaction.deleted_at.is_(None)
    ).group_by(Transaction.type)
    if start:
        stmt = stmt.where(Transaction.date >= start)
    totals = {t: (total, n) for t, total, n in db.execute(stmt).all()}
    income = totals.get(TransactionType.income, (0, 0))
    expense = totals.get(TransactionType.expense, (0, 0))
    return {
        "total_income": float(income[0]), "total_expense": float(expense[0]),
        "net_profit": float(income[0] - expense[0]), "currency": "UZS", "period": period,
        "from": start.isoformat() if start else None, "transactions_count": income[1] + expense[1],
    }
