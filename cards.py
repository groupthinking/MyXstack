"""Typed timeline cards.

A timeline card is how a team member asks a human to look at something —
and, when the card carries actions, to authorize something. Before this
module a card's entire presentation contract was `body: str` plus
`actions: List[str]`, so every member hand-concatenated its output into
one blob and no surface could render structure.

A card now carries `blocks`: a small closed set of content types that
covers what members actually produce (prose sections, key/value facts,
tabular results, link lists). The set is deliberately small — a surface
must be able to render every block type, so growing it is a real cost.

Two compatibility rules keep older readers working, and both are
load-bearing:

1. `body` is never dropped. When a card is written with `blocks`, `body`
   is populated with `derive_body(blocks)`. Anything that reads `body`
   today — the dispatcher, existing tests, plain curl — keeps working.

2. `action` on the wire keeps carrying the human *label*, not the id.
   Team members match on labels (`agents/team/shopping.py` matches
   `startswith("approve")` against "Approve Purchase";
   `agents/team/tradedesk.py` matches `== "approve"`). A surface posts
   `action_id` and the server resolves it back to the label via
   `resolve_action` before dispatching, so member code is untouched.

Legacy records are upgraded in memory on read by `normalize_card`; there
is no on-disk migration.
"""

import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 2

BLOCK_TYPES = ("text", "facts", "table", "links")

# Only these schemes may reach an anchor's href. Anything else — javascript:,
# data:, vbscript: — executes in the approval surface's origin.
SAFE_URL_SCHEMES = ("http", "https")


def is_safe_url(value: Any) -> bool:
    """True when `value` is an http(s) URL safe to render as a link.

    Shared by the Link model, the agents/base.py builder, and (mirrored) the
    browser renderer, so all three agree on what a renderable URL is."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return parsed.scheme.lower() in SAFE_URL_SCHEMES and bool(parsed.netloc)


# --------------------------------------------------------------------------
# Models (used by the API layer for validation)
# --------------------------------------------------------------------------


class Fact(BaseModel):
    key: str
    value: str


class Link(BaseModel):
    """A labelled hyperlink.

    `url` is restricted to http(s). Card content originates from model output
    over untrusted X mentions and is rendered into an anchor's href, so a
    `javascript:` or `data:` URL would execute in the approval surface's
    origin — where the bearer token that authorizes agent actions lives."""

    label: str
    url: str

    @field_validator("url")
    @classmethod
    def _safe_scheme(cls, value: str) -> str:
        if not is_safe_url(value):
            raise ValueError(
                f"unsupported URL scheme in {value!r}: only http and https are allowed"
            )
        return value


class TextBlock(BaseModel):
    """A prose section, e.g. label="Brief" for a research write-up."""

    type: Literal["text"] = "text"
    label: Optional[str] = None
    text: str


class FactsBlock(BaseModel):
    """Key/value pairs — the parameters of a proposed action."""

    type: Literal["facts"] = "facts"
    label: Optional[str] = None
    facts: List[Fact] = Field(default_factory=list)


class TableBlock(BaseModel):
    """Tabular results, e.g. product picks or ticker rows."""

    type: Literal["table"] = "table"
    label: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class LinksBlock(BaseModel):
    """A list of sources or destinations."""

    type: Literal["links"] = "links"
    label: Optional[str] = None
    links: List[Link] = Field(default_factory=list)


Block = Annotated[
    Union[TextBlock, FactsBlock, TableBlock, LinksBlock],
    Field(discriminator="type"),
]


class CardAction(BaseModel):
    """A button on a card.

    `id` is the stable machine identifier a surface posts back. `label` is
    what the human reads AND what team members match on, so changing a
    label is a behavioural change, not a cosmetic one.
    """

    id: str
    label: str
    style: Literal["primary", "danger", "neutral"] = "neutral"
    confirm: Optional[str] = None


# --------------------------------------------------------------------------
# Plain-dict helpers (used by the storage layer, which stays pydantic-free)
# --------------------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(label: str) -> str:
    """Derive a stable action id from a human label ("Approve Purchase" ->
    "approve-purchase"). Only used for legacy cards, whose actions are
    bare strings with no id of their own."""
    return _SLUG_STRIP.sub("-", str(label).lower()).strip("-") or "action"


def _render_block(block: Dict[str, Any]) -> str:
    kind = block.get("type")
    label = block.get("label")
    head = f"{label}:\n" if label else ""

    if kind == "text":
        return head + str(block.get("text", ""))

    if kind == "facts":
        lines = [f"{f.get('key')}: {f.get('value')}" for f in block.get("facts") or []]
        return head + "\n".join(lines)

    if kind == "table":
        columns = [str(c) for c in block.get("columns") or []]
        rows = block.get("rows") or []
        lines = []
        if columns:
            lines.append(" | ".join(columns))
        for row in rows:
            lines.append(" | ".join(str(cell) for cell in row))
        return head + "\n".join(lines)

    if kind == "links":
        lines = [f"{link.get('label')}: {link.get('url')}" for link in block.get("links") or []]
        return head + "\n".join(lines)

    # Unknown block type: never silently drop content a surface can't
    # render — fall back to its JSON-ish repr so the text form still
    # carries it.
    return head + str(block)


def derive_body(blocks: List[Dict[str, Any]]) -> str:
    """Render blocks to the plaintext `body` older readers still expect.

    Deliberately reproduces the "Label:\\n...\\n\\nLabel:\\n..." shape that
    members were building by hand, so the derived body is not a
    regression for anything reading it today."""
    return "\n\n".join(_render_block(b) for b in blocks if b)


class DuplicateActionIdError(ValueError):
    """Raised when a card offers two actions with the same id.

    `resolve_action` returns the first match, so duplicate ids would make a
    surface dispatch a different action than the human selected, and leave
    the later button permanently unreachable."""


def normalize_actions(actions: Any, *, strict: bool = False) -> List[Dict[str, Any]]:
    """Coerce either legacy `["Approve", "Reject"]` or typed action dicts
    into a uniform list of action dicts.

    strict=True rejects duplicate ids — used when accepting a new card at
    the API boundary. Reads of already-stored cards stay lenient so one bad
    historical record can't make the whole timeline unreadable."""
    if not isinstance(actions, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for action in actions:
        if isinstance(action, str):
            normalized.append(
                {"id": slugify(action), "label": action, "style": "neutral", "confirm": None}
            )
        elif isinstance(action, dict):
            label = action.get("label") or action.get("id") or "Action"
            normalized.append(
                {
                    "id": action.get("id") or slugify(label),
                    "label": label,
                    "style": action.get("style") or "neutral",
                    "confirm": action.get("confirm"),
                }
            )

    if strict:
        seen = set()
        for action in normalized:
            action_id = action["id"]
            if action_id in seen:
                raise DuplicateActionIdError(
                    f"duplicate action id {action_id!r}: each action on a card "
                    "must be addressable on its own"
                )
            seen.add(action_id)

    return normalized


def normalize_card(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a copy of a stored card in the current schema.

    Legacy records (no `blocks`) are upgraded in memory: `body` becomes a
    single text block and string actions gain derived ids. Nothing is
    written back — storage keeps whatever shape it already had."""
    if item is None:
        return None

    card = dict(item)
    blocks = card.get("blocks")

    if not isinstance(blocks, list) or not blocks:
        body = card.get("body") or ""
        card["blocks"] = [{"type": "text", "label": None, "text": body}] if body else []

    card["actions"] = normalize_actions(card.get("actions"))
    card["schema_version"] = card.get("schema_version") or SCHEMA_VERSION
    return card


def resolve_action(item: Optional[Dict[str, Any]], action_id: str) -> Optional[str]:
    """Map an action id back to the label team members match on.

    Returns None when the card has no such action — the caller must treat
    that as a rejected request rather than inventing a label, or a surface
    could trigger an action the card never offered."""
    card = normalize_card(item)
    if not card:
        return None
    for action in card.get("actions") or []:
        if action.get("id") == action_id:
            return action.get("label")
    return None
