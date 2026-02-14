import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests
import tweepy
from dotenv import load_dotenv
from tweepy.errors import HTTPException as TweepyHTTPException
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import mcp

LAST_SEEN_PATH = Path(os.getenv("XMCP_LAST_SEEN_PATH", "~/.xmcp/last_seen.txt")).expanduser()
POLL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
PAYMENT_REQUIRED_BACKOFF_SECONDS = int(os.getenv("X_PAYMENT_REQUIRED_BACKOFF_SECONDS", "900"))

PROCESSED_MENTIONS_PATH = Path(os.getenv("XMCP_PROCESSED_MENTIONS_PATH", "~/.xmcp/processed_mentions.txt")).expanduser()

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


def load_processed_mentions() -> set[str]:
    if not PROCESSED_MENTIONS_PATH.exists():
        return set()
    with PROCESSED_MENTIONS_PATH.open("r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_processed_mention(mention_id: str) -> None:
    PROCESSED_MENTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_MENTIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{mention_id}\n")


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


def get_grok_reply(prompt: str) -> str:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        return "Missing XAI_API_KEY."
    model = os.getenv("XAI_MODEL", "grok-4-1-fast")
    server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")

    client = Client(api_key=api_key)
    chat = client.chat.create(
        model=model,
        tools=[mcp(server_url=server_url)],
    )
    chat.append(user(prompt))

    response_text = ""
    for _, chunk in chat.stream():
        if chunk.content:
            response_text += chunk.content
    return response_text.strip() or "Thinking..."


def push_timeline_card(title: str, body: str, metadata: dict) -> None:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8000")
    user_id = os.getenv("TIMELINE_USER_ID", "default")
    payload = {
        "user_id": user_id,
        "title": title,
        "body": body,
        "posted_by": "x-agent",
        "actions": ["Approve", "Reject", "Snooze"],
        "metadata": metadata,
    }
    requests.post(f"{timeline_url}/v1/timeline/items", json=payload, timeout=10)


def ensure_agent_registered() -> None:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8000")
    payload = {
        "id": "x-agent",
        "name": "X Agent",
        "description": "Handles @mentions and X actions.",
        "status": "online",
        "endpoint": "x",
        "tags": ["x", "social"],
    }
    requests.post(f"{timeline_url}/v1/a2a/agents", json=payload, timeout=10)


def main() -> None:
    load_env()
    client = build_client()
    me = client.get_me().data
    if not me:
        raise RuntimeError("Could not resolve authenticated X user for listener")
    bot_id = me.id
    ensure_agent_registered()

    last_seen = load_last_seen()
    start_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    if last_seen:
        try:
            start_time = datetime.fromisoformat(last_seen)
        except ValueError:
            pass

    processed_mentions = load_processed_mentions()

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
            mention_id_str = str(mention.id)
            if mention_id_str in processed_mentions:
                print(f"Skipping already processed mention {mention.id}", flush=True)
                continue

            context = mention.text
            prompt = f"""
You are an autonomous X agent bot. You were mentioned in this thread:

{context}

Analyze the request/intent. Use available tools to respond helpfully.
Always reply directly to the mentioning post. Be concise and actionable.
"""
            try:
                grok_reply = get_grok_reply(prompt)
            except Exception as exc:
                print(f"Error getting Grok reply for mention {mention.id}: {exc}", flush=True)
                grok_reply = "Sorry, I'm having trouble processing that. Try again or DM me."

            try:
                client.create_tweet(
                    text=grok_reply[:280],
                    in_reply_to_tweet_id=mention.id,
                )
                processed_mentions.add(mention_id_str)
                save_processed_mention(mention_id_str)
            except Exception as exc:
                print(f"Error replying to mention {mention.id}: {exc}", flush=True)

            try:
                push_timeline_card(
                    title=f"New mention {mention.id}",
                    body=context,
                    metadata={
                        "mention_id": mention.id,
                        "author_id": mention.author_id,
                        "conversation_id": mention.conversation_id,
                        "reply_preview": grok_reply[:280],
                    },
                )
            except Exception as exc:
                print(f"Error pushing timeline card for mention {mention.id}: {exc}", flush=True)

            start_time = mention.created_at or datetime.now(timezone.utc)
            save_last_seen(start_time.isoformat())

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
