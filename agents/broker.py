"""Paper-trading broker: the default (and only built-in) trade executor.

Every approved trade is recorded as a simulated fill in a local JSON
ledger. No live orders are ever placed. A real broker can be plugged in
by replacing PaperBroker with an adapter exposing the same interface.
"""

import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LEDGER_LOCK = threading.Lock()


@contextmanager
def _ledger_file_lock(ledger_path: Path):
    """Cross-process advisory lock so concurrent dispatchers can't corrupt
    the ledger (fcntl is Unix-only; degrades to the thread lock elsewhere)."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:
        yield
        return
    lock_file = ledger_path.with_suffix(".lock")
    with open(lock_file, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class PaperBroker:
    def __init__(self, ledger_path: Optional[str] = None):
        raw = ledger_path or os.getenv("PAPER_TRADES_PATH", "~/.xmcp/paper_trades.json")
        self.ledger_path = Path(raw).expanduser()

    def _read(self) -> List[Dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        try:
            data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            # Never silently discard trade history: preserve the corrupt
            # file for reconciliation and start a fresh ledger.
            backup = self.ledger_path.with_suffix(
                f".corrupt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            )
            self.ledger_path.rename(backup)
            print(f"Ledger corrupt ({exc}); preserved as {backup}", flush=True)
            return []
        return data if isinstance(data, list) else []

    def _write(self, fills: List[Dict[str, Any]]) -> None:
        """Atomic replace so a mid-write crash can't truncate the ledger."""
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(fills, indent=2), encoding="utf-8")
        os.replace(tmp, self.ledger_path)

    def execute(
        self, ticker: str, side: str, quantity: float, key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a simulated fill.

        key is an idempotency token (e.g. the timeline card id): if a fill
        with the same key already exists, it is returned with
        duplicate=True instead of booking a second fill.
        """
        with _LEDGER_LOCK, _ledger_file_lock(self.ledger_path):
            fills = self._read()
            if key:
                for existing in fills:
                    if existing.get("key") == key:
                        return {**existing, "duplicate": True}
            fill = {
                "id": str(uuid.uuid4()),
                "key": key,
                "ticker": ticker.upper(),
                "side": side.lower(),
                "quantity": quantity,
                "status": "filled",
                "venue": "paper",
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            fills.insert(0, fill)
            self._write(fills)
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
