import csv  # noqa: F401
import io  # noqa: F401
from datetime import date, datetime  # noqa: F401
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from fastapi.responses import Response  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import *  # noqa: F401,F403
from app.db import fake  # noqa: F401
from app.schemas import *  # noqa: F401,F403

router = APIRouter()

# ── FINANCE ───────────────────────────────────
@router.get("/finance/transactions", tags=["💰 Finance"], response_model=List[Transaction],
         summary="Moliyaviy tranzaksiyalar", description="Barcha daromad va xarajatlarni ko'rish.")
def get_transactions(
    type: Optional[TransactionType] = Query(None),
    category: Optional[str] = Query(None),
    _=Depends(get_current_user)
):
    results = fake.fake_transactions
    if type:
        results = [t for t in results if t.type == type]
    if category:
        results = [t for t in results if t.category == category]
    return results

@router.post("/finance/transactions", tags=["💰 Finance"], response_model=Transaction, status_code=201,
          summary="Yangi tranzaksiya qo'shish")
def create_transaction(data: TransactionCreate, _=Depends(get_current_user)):
    tx = Transaction(**data.model_dump(), id=new_id(),
                     created_at=datetime.now().isoformat()[:10])
    fake.fake_transactions.append(tx)
    return tx

@router.get("/finance/summary", tags=["💰 Finance"],
         summary="Moliyaviy xulosа",
         description="Jami daromad, xarajat va foyda ko'rsatkichlarini olish.")
def get_finance_summary(_=Depends(get_current_user)):
    income = sum(t.amount for t in fake.fake_transactions if t.type == TransactionType.income)
    expense = sum(t.amount for t in fake.fake_transactions if t.type == TransactionType.expense)
    return {
        "total_income": income,
        "total_expense": expense,
        "net_profit": income - expense,
        "currency": "UZS",
        "period": "2026-02",
        "transactions_count": len(fake.fake_transactions)
    }
