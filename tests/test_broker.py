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
