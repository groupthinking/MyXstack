from agents.base import MentionContext
from agents.broker import PaperBroker
from agents.team.tradedesk import TradeDeskAgent, parse_trade_command


def test_parse_ticker_first():
    assert parse_trade_command("@Tradedesk $TSLA buy 100") == {
        "ticker": "TSLA",
        "side": "buy",
        "quantity": 100.0,
    }


def test_parse_side_first():
    assert parse_trade_command("@Tradedesk sell $btc 0.5") == {
        "ticker": "BTC",
        "side": "sell",
        "quantity": 0.5,
    }


def test_parse_defaults_quantity_to_one():
    assert parse_trade_command("$NVDA buy")["quantity"] == 1.0


def test_parse_requires_cashtag():
    assert parse_trade_command("buy it now") is None
    assert parse_trade_command("@Tradedesk hello") is None


def test_mention_creates_approval_card(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEDESK_USE_GROK", "0")
    agent = TradeDeskAgent(broker=PaperBroker(str(tmp_path / "trades.json")))
    reply = agent.handle_mention(
        MentionContext(text="@Tradedesk $TSLA buy 10", mention_id=1, author_id=2)
    )
    assert "pending human approval" in reply.text.lower()
    assert reply.card["actions"] == ["Approve", "Reject"]
    meta = reply.card["metadata"]
    assert meta["agent_id"] == "tradedesk"
    assert meta["ticker"] == "TSLA"
    assert meta["side"] == "buy"
    assert meta["quantity"] == 10.0


def test_unparseable_mention_returns_usage(monkeypatch):
    monkeypatch.setenv("TRADEDESK_USE_GROK", "0")
    agent = TradeDeskAgent(broker=PaperBroker("/dev/null"))
    reply = agent.handle_mention(MentionContext(text="@Tradedesk moon when"))
    assert reply.card is None
    assert "$TICKER" in reply.text


def test_approve_executes_paper_trade(tmp_path):
    broker = PaperBroker(str(tmp_path / "trades.json"))
    agent = TradeDeskAgent(broker=broker)
    item = {
        "id": "item-1",
        "metadata": {
            "agent_id": "tradedesk",
            "action_type": "trade",
            "ticker": "TSLA",
            "side": "buy",
            "quantity": 10,
        },
    }
    result = agent.execute_action(item, "Approve")
    assert "Executed" in result
    assert broker.positions() == {"TSLA": 10.0}


def test_reject_places_no_order(tmp_path):
    broker = PaperBroker(str(tmp_path / "trades.json"))
    agent = TradeDeskAgent(broker=broker)
    item = {
        "metadata": {
            "agent_id": "tradedesk",
            "action_type": "trade",
            "ticker": "TSLA",
            "side": "sell",
            "quantity": 5,
        }
    }
    result = agent.execute_action(item, "Reject")
    assert "cancelled" in result.lower()
    assert broker.positions() == {}


def test_non_trade_card_is_ignored():
    agent = TradeDeskAgent(broker=PaperBroker("/dev/null"))
    assert agent.execute_action({"metadata": {"action_type": "purchase"}}, "Approve") is None
