import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import payme

router = APIRouter()


@router.post("/payments/payme", tags=["💳 Payme"], include_in_schema=True, summary="Payme Merchant API (JSON-RPC 2.0, Payme chaqiradi)",
             description="`Authorization: Basic base64('Paycom:KEY')`. Metodlar: CheckPerformTransaction, CreateTransaction, "
                         "PerformTransaction, CancelTransaction, CheckTransaction, GetStatement. Javob har doim HTTP 200.")
async def payme_endpoint(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    try:
        payload = json.loads(raw)
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": payme.PaymeError(payme.ERR_PARSE).body()})
    rpc_id = payload.get("id") if isinstance(payload, dict) else None
    if not payme.authorized(request.headers.get("authorization")):
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "error": payme.PaymeError(payme.ERR_AUTH).body()})
    return JSONResponse(payme.handle(db, payload))
