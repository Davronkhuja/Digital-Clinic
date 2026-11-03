from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# DB'da numeric(14,2) (Decimal); JSON'da frontend kutgan son
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
