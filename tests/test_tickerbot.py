from agents.base import MentionContext
from agents.team.tickerbot import TickerBot


def test_handle_mention_single_ticker():
    bot = TickerBot()
    reply = bot.handle_mention(MentionContext(text="@TickerBot $TSLA"))
    assert reply.text == "$TSLA: live chatter → x.com/search?q=%24TSLA&f=live"
    assert reply.card is None


def test_handle_mention_multiple_tickers_deduped_and_sorted():
    bot = TickerBot()
    reply = bot.handle_mention(MentionContext(text="$tsla $TSLA $NVDA $btc"))
    lines = reply.text.splitlines()
    assert lines == [
        "$BTC: live chatter → x.com/search?q=%24BTC&f=live",
        "$NVDA: live chatter → x.com/search?q=%24NVDA&f=live",
        "$TSLA: live chatter → x.com/search?q=%24TSLA&f=live",
    ]


def test_handle_mention_no_ticker_returns_usage():
    bot = TickerBot()
    reply = bot.handle_mention(MentionContext(text="@TickerBot hello there"))
    assert reply.text == "Usage: @TickerBot $TICKER — e.g. @TickerBot $TSLA"


def test_handle_mention_ignores_bare_dollar_amounts_without_letters():
    bot = TickerBot()
    reply = bot.handle_mention(MentionContext(text="that costs $100"))
    assert reply.text.startswith("Usage:")


def test_profile_is_classified_as_bot():
    bot = TickerBot()
    assert bot.profile.kind == "bot"
    assert bot.profile.id == "tickerbot"


def test_handle_uses_tickerbot_handle_env_var(monkeypatch):
    monkeypatch.setenv("TICKERBOT_HANDLE", "Cashtags")
    bot = TickerBot()
    assert bot.profile.handle == "Cashtags"