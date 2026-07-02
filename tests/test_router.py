from agents.base import MentionContext
from agents.registry import build_team, find_member, get_team, route_mention
from agents.router import find_target


def test_route_to_tradedesk_by_handle():
    member = route_mention(MentionContext(text="@MyXstack @Tradedesk $TSLA buy 100"))
    assert member.profile.id == "tradedesk"


def test_route_is_case_insensitive():
    member = route_mention(MentionContext(text="hey @tradedesk sell $BTC"))
    assert member.profile.id == "tradedesk"


def test_route_requires_word_boundary():
    team = build_team()
    member = find_target("@TradedeskFanClub what do you think?", team)
    assert member is None


def test_route_falls_back_to_general_agent():
    member = route_mention(MentionContext(text="@MyXstack what's the weather?"))
    assert member.profile.id == "x-agent"


def test_route_to_bot():
    member = route_mention(MentionContext(text="@TickerBot $NVDA"))
    assert member.profile.id == "tickerbot"
    assert member.profile.kind == "bot"


def test_team_classification():
    kinds = {m.profile.id: m.profile.kind for m in get_team()}
    assert kinds["tradedesk"] == "agent"
    assert kinds["research"] == "agent"
    assert kinds["shopping"] == "agent"
    assert kinds["tickerbot"] == "bot"


def test_multi_handle_routes_to_earliest_tag():
    team = build_team()
    member = find_target("@Research @Tradedesk what about $TSLA?", team)
    assert member.profile.id == "research"
    member = find_target("@Tradedesk @Research what about $TSLA?", team)
    assert member.profile.id == "tradedesk"


def test_find_member():
    assert find_member("tradedesk").profile.name == "Trade Desk"
    assert find_member("nope") is None
    assert find_member(None) is None
