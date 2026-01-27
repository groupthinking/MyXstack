import os
import time
from datetime import datetime, timedelta

import tweepy


def build_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_OAUTH_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_OAUTH_ACCESS_TOKEN_SECRET"),
    )


def fetch_thread_context(client: tweepy.Client, conversation_id: str) -> str:
    thread = client.search_recent_tweets(
        query=f"conversation_id:{conversation_id}",
        tweet_fields=["text", "author_id"],
    )
    tweets = thread.data or []
    return "\n".join(tweet.text for tweet in tweets)


def main() -> None:
    client = build_client()
    bot = client.get_me().data
    bot_id = bot.id

    last_checked = datetime.utcnow() - timedelta(minutes=10)

    while True:
        mentions = client.get_users_mentions(
            id=bot_id,
            since_id=None,
            tweet_fields=["created_at", "conversation_id"],
        ).data or []

        for mention in mentions:
            if mention.created_at and mention.created_at <= last_checked:
                continue

            context = fetch_thread_context(client, mention.conversation_id)
            prompt = (
                "You were tagged here:\n"
                f"{context}\n\n"
                "Reason step-by-step and use X tools via MCP to respond autonomously.\n"
                "Server: http://127.0.0.1:8000/mcp"
            )

            # TODO: Replace with Grok invocation via MCP.
            _ = prompt

            client.create_tweet(
                text="Processing your tag... (full response coming soon)",
                in_reply_to_tweet_id=mention.id,
            )

        last_checked = datetime.utcnow()
        time.sleep(60)


if __name__ == "__main__":
    main()
