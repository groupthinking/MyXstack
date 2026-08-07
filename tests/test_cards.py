from cards import (
    SCHEMA_VERSION,
    derive_body,
    normalize_actions,
    normalize_card,
    resolve_action,
    slugify,
)


def test_slugify_derives_stable_ids():
    assert slugify("Approve Purchase") == "approve-purchase"
    assert slugify("Reject") == "reject"
    # Never produce an empty id, or an action becomes unaddressable.
    assert slugify("!!!") == "action"


def test_derive_body_renders_every_block_type():
    body = derive_body(
        [
            {"type": "text", "label": "Question", "text": "why is it down?"},
            {"type": "facts", "label": "Order", "facts": [{"key": "Side", "value": "BUY"}]},
            {"type": "table", "columns": ["Item", "Price"], "rows": [["Shoe", "$120"]]},
            {"type": "links", "links": [{"label": "src", "url": "https://x.com"}]},
        ]
    )
    assert "Question:\nwhy is it down?" in body
    assert "Order:\nSide: BUY" in body
    assert "Item | Price" in body
    assert "Shoe | $120" in body
    assert "src: https://x.com" in body


def test_derive_body_keeps_unknown_block_content():
    # A surface may not render an unknown block, but its content must never
    # vanish from the text form.
    body = derive_body([{"type": "future", "payload": "important"}])
    assert "important" in body


def test_normalize_actions_accepts_legacy_strings_and_typed_dicts():
    assert normalize_actions(["Approve Purchase"]) == [
        {"id": "approve-purchase", "label": "Approve Purchase", "style": "neutral", "confirm": None}
    ]
    typed = normalize_actions([{"id": "approve", "label": "Approve", "style": "primary"}])
    assert typed[0]["id"] == "approve"
    assert typed[0]["style"] == "primary"
    assert normalize_actions(None) == []


def test_normalize_card_upgrades_a_legacy_record():
    legacy = {
        "id": "abc",
        "title": "Trade proposal",
        "body": "BUY 10 $TSLA",
        "actions": ["Approve", "Reject"],
    }
    card = normalize_card(legacy)

    assert card["schema_version"] == SCHEMA_VERSION
    assert card["blocks"] == [{"type": "text", "label": None, "text": "BUY 10 $TSLA"}]
    assert [a["id"] for a in card["actions"]] == ["approve", "reject"]
    # The original record is not mutated in place.
    assert legacy["actions"] == ["Approve", "Reject"]


def test_normalize_card_leaves_typed_blocks_alone():
    blocks = [{"type": "facts", "label": "Order", "facts": [{"key": "Side", "value": "BUY"}]}]
    card = normalize_card({"blocks": blocks, "body": "derived", "actions": []})
    assert card["blocks"] == blocks


def test_resolve_action_maps_id_to_the_label_members_match_on():
    card = {
        "body": "picks",
        "actions": [
            {"id": "approve", "label": "Approve Purchase"},
            {"id": "reject", "label": "Reject"},
        ],
    }
    assert resolve_action(card, "approve") == "Approve Purchase"
    assert resolve_action(card, "reject") == "Reject"


def test_resolve_action_rejects_an_action_the_card_never_offered():
    card = {"body": "brief", "actions": []}
    assert resolve_action(card, "approve") is None
    assert resolve_action(None, "approve") is None


def test_resolve_action_works_on_legacy_string_actions():
    # A card written before typed actions must still be approvable from a
    # surface that only knows how to post ids.
    card = {"body": "x", "actions": ["Approve", "Reject"]}
    assert resolve_action(card, "approve") == "Approve"
