import os
import time
from datetime import datetime, timedelta, timezone

import tweepy
from tweepy.errors import TweepyException


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=require_env("X_BEARER_TOKEN"),
        consumer_key=require_env("X_API_KEY"),
        consumer_secret=require_env("X_API_SECRET"),
        access_token=require_env("X_OAUTH_ACCESS_TOKEN"),
        access_token_secret=require_env("X_OAUTH_ACCESS_TOKEN_SECRET"),
    )


def fetch_thread_context(client: tweepy.Client, conversation_id: str) -> str:
    try:
        thread = client.search_recent_tweets(
            query=f"conversation_id:{conversation_id}",
            tweet_fields=["text", "author_id"],
        )
    except TweepyException as exc:
        print(f"Failed to fetch thread context: {exc}")
        return ""
    tweets = thread.data or []
    return "\n".join(tweet.text for tweet in tweets)


def main() -> None:
    try:
        client = build_client()
        bot = client.get_me().data
    except (RuntimeError, TweepyException) as exc:
        print(f"Unable to initialize X client: {exc}")
        return

    if not bot:
        print("Unable to fetch bot user info.")
        return

    bot_id = bot.id
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    last_seen_id = None
    last_checked = datetime.now(timezone.utc) - timedelta(minutes=10)

    while True:
        try:
            mentions_response = client.get_users_mentions(
                id=bot_id,
                since_id=last_seen_id,
                tweet_fields=["created_at", "conversation_id"],
            )
        except TweepyException as exc:
            print(f"Failed to fetch mentions: {exc}")
            time.sleep(poll_interval)
            continue

        mentions = mentions_response.data or []
        for mention in reversed(mentions):
            if mention.created_at and mention.created_at <= last_checked:
                continue
            if not mention.conversation_id:
                continue

            context = fetch_thread_context(client, str(mention.conversation_id))
            prompt = (
                "You were tagged here:\n"
                f"{context}\n\n"
                "Reason through this step-by-step and use X tools via xMCP to respond autonomously.\n"
                "Server: http://127.0.0.1:8000/mcp"
            )

            # TODO: Replace with Grok invocation via xMCP.
            _ = prompt

            try:
                client.create_tweet(
                    text="Processing your tag... (full response coming soon)",
                    in_reply_to_tweet_id=mention.id,
                )
            except TweepyException as exc:
                print(f"Failed to reply to mention {mention.id}: {exc}")

        if mentions:
            last_seen_id = max(int(mention.id) for mention in mentions)
        last_checked = datetime.now(timezone.utc)
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
