import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests
import tweepy
from dotenv import load_dotenv
from tweepy.errors import HTTPException as TweepyHTTPException

from agents.base import MentionContext
from agents.registry import register_team, route_mention

LAST_SEEN_PATH = Path(os.getenv("XMCP_LAST_SEEN_PATH", "~/.xmcp/last_seen.txt")).expanduser()
POLL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
PAYMENT_REQUIRED_BACKOFF_SECONDS = int(os.getenv("X_PAYMENT_REQUIRED_BACKOFF_SECONDS", "900"))


def load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def save_last_seen(value: str) -> None:
    LAST_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_SEEN_PATH.write_text(value, encoding="utf-8")


def load_last_seen() -> Optional[str]:
    if not LAST_SEEN_PATH.exists():
        return None
    return LAST_SEEN_PATH.read_text(encoding="utf-8").strip() or None


def build_client() -> tweepy.Client:
    access_token = os.getenv("X_ACCESS_TOKEN") or os.getenv("X_OAUTH_ACCESS_TOKEN")
    access_secret = os.getenv("X_ACCESS_SECRET") or os.getenv("X_OAUTH_ACCESS_TOKEN_SECRET")
    return tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=access_token,
        access_token_secret=access_secret,
        wait_on_rate_limit=True,
    )


def push_timeline_card(card: dict, posted_by: str) -> None:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8080")
    user_id = os.getenv("TIMELINE_USER_ID", "default")
    payload = {
        "user_id": user_id,
        "title": card.get("title", "Untitled"),
        "body": card.get("body", ""),
        "posted_by": posted_by,
        "actions": card.get("actions", []),
        "metadata": card.get("metadata", {}),
    }
    response = requests.post(f"{timeline_url}/v1/timeline/items", json=payload, timeout=10)
    # Surface 4xx/5xx as failures so the caller holds the watermark and
    # retries — a lost card would silently defeat the approval gate.
    response.raise_for_status()


def process_mention(client: tweepy.Client, mention) -> bool:
    """Route one mention to its team member and deliver the results.

    Returns False when the approval card could not be pushed — the caller
    must then NOT advance the last-seen watermark, so the mention is
    retried next poll instead of its approval-gated proposal being lost.
    The card is pushed before the X reply for the same reason: the card is
    the safety-critical artifact.
    """
    context = MentionContext(
        text=mention.text,
        mention_id=mention.id,
        author_id=mention.author_id,
        conversation_id=mention.conversation_id,
    )
    member = route_mention(context)
    print(
        f"Mention {mention.id} routed to {member.profile.id} ({member.profile.kind})",
        flush=True,
    )
    try:
        reply = member.handle_mention(context)
    except Exception as exc:
        print(
            f"Error from agent {member.profile.id} for mention {mention.id}: {exc}",
            flush=True,
        )
        return True

    if reply.card:
        try:
            push_timeline_card(reply.card, posted_by=member.profile.id)
        except Exception as exc:
            print(
                f"Error pushing timeline card for mention {mention.id}: {exc}; will retry",
                flush=True,
            )
            return False

    try:
        client.create_tweet(
            text=reply.text[:280],
            in_reply_to_tweet_id=mention.id,
        )
    except Exception as exc:
        print(f"Error replying to mention {mention.id}: {exc}", flush=True)
    return True


def main() -> None:
    load_env()
    client = build_client()
    me = client.get_me().data
    if not me:
        raise RuntimeError("Could not resolve authenticated X user for listener")
    bot_id = me.id
    register_team()

    last_seen = load_last_seen()
    start_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    if last_seen:
        try:
            start_time = datetime.fromisoformat(last_seen)
        except ValueError:
            pass

    while True:
        try:
            mentions = client.get_users_mentions(
                id=bot_id,
                start_time=start_time,
                tweet_fields=["conversation_id", "created_at", "author_id", "text"],
            )
        except TweepyHTTPException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 402:
                # Avoid crash-looping if the X account does not have API credits enabled yet.
                print(
                    f"X API returned 402 Payment Required. Backing off for {PAYMENT_REQUIRED_BACKOFF_SECONDS}s.",
                    flush=True,
                )
                time.sleep(PAYMENT_REQUIRED_BACKOFF_SECONDS)
                continue
            print(f"X API error fetching mentions: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
            continue
        except Exception as exc:
            print(f"Unexpected error fetching mentions: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
            continue

        for mention in mentions.data or []:
            if not process_mention(client, mention):
                # Card push failed: stop here so this mention (and later
                # ones) are retried on the next poll.
                break
            start_time = mention.created_at or datetime.now(timezone.utc)
            save_last_seen(start_time.isoformat())

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
