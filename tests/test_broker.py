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


def test_positions_on_missing_ledger_file_is_empty(tmp_path):
    broker = PaperBroker(str(tmp_path / "does-not-exist.json"))
    assert broker.positions() == {}


def test_ledger_that_is_valid_json_but_not_a_list_is_treated_as_empty(tmp_path):
    path = tmp_path / "trades.json"
    path.write_text('{"unexpected": "shape"}', encoding="utf-8")
    broker = PaperBroker(str(path))
    # A non-list JSON payload is not "corrupt" (it parses fine), so it is
    # not backed up - _read() just falls back to an empty ledger.
    assert broker.positions() == {}
    broker.execute("TSLA", "buy", 1)
    assert broker.positions() == {"TSLA": 1.0}


def test_default_ledger_path_uses_env_var(monkeypatch, tmp_path):
    custom_path = tmp_path / "custom" / "trades.json"
    monkeypatch.setenv("PAPER_TRADES_PATH", str(custom_path))
    broker = PaperBroker()
    assert broker.ledger_path == custom_path.expanduser()
