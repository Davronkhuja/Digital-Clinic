import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import click

router = APIRouter()


@router.post("/payments/click", tags=["💳 Click"], summary="Click SHOP API (Prepare/Complete; Click chaqiradi)",
             description="`action=0` Prepare, `action=1` Complete. Form-urlencoded yoki JSON. Imzo `sign_string` (md5) tekshiriladi. "
                         "Javob har doim HTTP 200, natija `error`/`error_note` da.")
async def click_endpoint(request: Request, db: Session = Depends(get_db)):
    ctype = request.headers.get("content-type", "")
    if "json" in ctype:
        try:
            params = json.loads(await request.body())
        except ValueError:
            params = {}
    else:
        params = dict((await request.form()).items())
    params = {k: ("" if v is None else str(v)) for k, v in params.items()} if isinstance(params, dict) else {}
    return click.handle(db, params)
