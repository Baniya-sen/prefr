import os
import json
import asyncio
from pathlib import Path

import tiktoken
from dotenv import load_dotenv
from openai import AsyncOpenAI

from preferences_engine.prompt import CLASSIFIER_PROMPT


def load_schema() -> dict:
    path = Path(__file__).resolve().parent.parent / "classification" / "CLASSIFY_SCHEMA.json"

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_config() -> tuple[str, str, str, str, bool]:
    load_dotenv()

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    opencode_key = os.getenv("OPENCODE_GO_API_KEY")

    if openrouter_key:
        return (
            "https://openrouter.ai/api/v1",
            openrouter_key,
            os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"),
            "classifier-session",
            True,
        )

    if opencode_key:
        return (
            "https://opencode.ai/zen/go/v1",
            opencode_key,
            os.getenv("OPENCODE_GO_MODEL", "deepseek-v4-flash"),
            "classifier-session",
            False,
        )

    raise RuntimeError(
        "Set OPENROUTER_API_KEY or OPENCODE_GO_API_KEY"
    )


def create_client(api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
    )


def build_request(
        base: str,
        model: str,
        message: str,
        schema: dict,
        session_id: str,
        use_session_id: bool,
) -> dict:
    request = {
        "model": model,
        "messages": [
            {"role": "system", "content": CLASSIFIER_PROMPT},
            {"role": "user", "content": message},
        ],
        "temperature": 0.1,
    }

    extra_body = {}

    if "openrouter.ai" in base:
        request["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "classifier",
                "strict": True,
                "schema": schema,
            },
        }
        extra_body["reasoning"] = {
            "effort": "none",
        }

        if use_session_id:
            extra_body["session_id"] = session_id

    else:
        extra_body["thinking"] = {
            "type": "disabled",
        }

    if extra_body:
        request["extra_body"] = extra_body

    return request


def print_usage(response) -> None:
    if not response.usage:
        return

    details = getattr(response.usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) if details else 0
    written = getattr(details, "cache_write_tokens", 0) if details else 0

    print(f"cached tokens: {cached}")
    print(f"cache write tokens: {written}")


async def classify(
        client: AsyncOpenAI,
        base: str,
        model: str,
        message: str,
        schema: dict,
        session_id: str,
        use_session_id: bool,
) -> str:
    request = build_request(
        base=base,
        model=model,
        message=message,
        schema=schema,
        session_id=session_id,
        use_session_id=use_session_id,
    )

    response = await client.chat.completions.create(**request)

    print_usage(response)

    return response.choices[0].message.content or ""


def print_prompt_info() -> None:
    encoder = tiktoken.get_encoding("o200k_base")
    tokens = len(encoder.encode(CLASSIFIER_PROMPT))

    print(f"System prompt tokens: {tokens}")


async def main() -> None:
    schema = load_schema()

    base_url, api_key, model, session_id, use_session_id = load_config()
    client = create_client(api_key, base_url)

    print(f"Model: {model}")
    print_prompt_info()
    print("Warming prompt cache...")

    await classify(
        client=client,
        base=base_url,
        model=model,
        message="",
        schema=schema,
        session_id=session_id,
        use_session_id=use_session_id,
    )

    print("Ready.\n")

    while True:
        message = input("User: ")

        if message == "/exit":
            break

        reply = await classify(
            client=client,
            base=base_url,
            model=model,
            message=message,
            schema=schema,
            session_id=session_id,
            use_session_id=use_session_id,
        )

        print(f"{reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
