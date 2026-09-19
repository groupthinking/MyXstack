from agents.broker import PaperBroker


def test_execute_records_fill(tmp_path):
    broker = PaperBroker(str(tmp_path / "trades.json"))
    fill = broker.execute("tsla", "BUY", 10)
    assert fill["ticker"] == "TSLA"
    assert fill["side"] == "buy"
    assert fill["status"] == "filled"
    assert fill["venue"] == "paper"


def test_positions_aggregate_across_fills(tmp_path):
    broker = PaperBroker(str(tmp_path / "trades.json"))
    broker.execute("TSLA", "buy", 10)
    broker.execute("TSLA", "sell", 4)
    broker.execute("NVDA", "buy", 2)
    assert broker.positions() == {"TSLA": 6.0, "NVDA": 2.0}


def test_same_key_returns_existing_fill(tmp_path):
    broker = PaperBroker(str(tmp_path / "trades.json"))
    first = broker.execute("TSLA", "buy", 10, key="card-1")
    second = broker.execute("TSLA", "buy", 10, key="card-1")
    assert second["duplicate"] is True
    assert second["id"] == first["id"]
    assert broker.positions() == {"TSLA": 10.0}


def test_corrupt_ledger_is_preserved_not_wiped(tmp_path):
    path = tmp_path / "trades.json"
    path.write_text("{not json", encoding="utf-8")
    broker = PaperBroker(str(path))
    broker.execute("TSLA", "buy", 1)
    backups = list(tmp_path.glob("trades.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not json"
    assert broker.positions() == {"TSLA": 1.0}
