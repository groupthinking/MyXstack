"""Paper-trading broker: the default (and only built-in) trade executor.

Every approved trade is recorded as a simulated fill in a local JSON
ledger. No live orders are ever placed. A real broker can be plugged in
by replacing PaperBroker with an adapter exposing the same interface.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LEDGER_LOCK = threading.Lock()


class PaperBroker:
    def __init__(self, ledger_path: Optional[str] = None):
        raw = ledger_path or os.getenv("PAPER_TRADES_PATH", "~/.xmcp/paper_trades.json")
        self.ledger_path = Path(raw).expanduser()

    def _read(self) -> List[Dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        try:
            data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def execute(self, ticker: str, side: str, quantity: float) -> Dict[str, Any]:
        fill = {
            "id": str(uuid.uuid4()),
            "ticker": ticker.upper(),
            "side": side.lower(),
            "quantity": quantity,
            "status": "filled",
            "venue": "paper",
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        with _LEDGER_LOCK:
            fills = self._read()
            fills.insert(0, fill)
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            self.ledger_path.write_text(json.dumps(fills, indent=2), encoding="utf-8")
        return fill

    def positions(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        with _LEDGER_LOCK:
            fills = self._read()
        for fill in fills:
            sign = 1 if fill.get("side") == "buy" else -1
            ticker = fill.get("ticker", "?")
            totals[ticker] = totals.get(ticker, 0) + sign * float(fill.get("quantity", 0))
        return totals
