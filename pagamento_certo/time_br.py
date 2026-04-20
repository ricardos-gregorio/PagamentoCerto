from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

# Lembretes seguem o calendário do Brasil (mesmo no GitHub Actions, runner em UTC).
TZ_BR = ZoneInfo("America/Sao_Paulo")


def today_brazil() -> date:
    return datetime.now(TZ_BR).date()
