"""
LLM Router
----------
Supports two backends:
  - Groq  (free cloud, 14k req/day, fast, better instruction following)
  - Ollama (local, completely free, offline capable)

Set LLM_BACKEND in .env to "groq" or "ollama".
Falls back to Ollama if Groq fails or key is missing.
"""

import os
import time


BACKEND  = os.getenv("LLM_BACKEND", "ollama").lower()
MODEL_GROQ   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MODEL_OLLAMA = os.getenv("OLLAMA_MODEL", "llama3.1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SYSTEM_PROMPT = """You are a SQL code completion engine for Snowflake and dbt.
Continue the SQL exactly where it stops.
Return ONLY raw SQL. No explanation. No markdown. No comments outside SQL."""


def ask_llm(prompt: str, retries: int = 3) -> str:
    """
    Send prompt to configured LLM backend.
    Tries Groq first if configured, falls back to Ollama.
    """

    if BACKEND == "groq" and GROQ_API_KEY:
        try:
            return _ask_groq(prompt, retries)
        except Exception as e:
            print(f"  Groq failed ({e}), falling back to Ollama...")

    return _ask_ollama(prompt, retries)


def _ask_groq(prompt: str, retries: int) -> str:
    """Call Groq API — free tier, fast, good instruction following."""

    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_GROQ,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ],
                temperature=0,
                max_tokens=1500,
            )
            return response.choices[0].message.content

        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2 ** attempt)

    return ""


def _ask_ollama(prompt: str, retries: int) -> str:
    """Call local Ollama instance."""

    import ollama

    for attempt in range(retries):
        try:
            response = ollama.chat(
                model=MODEL_OLLAMA,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ],
                options={"temperature": 0}
            )
            return response["message"]["content"]

        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2)

    return ""


def get_backend_info() -> dict:
    """Return info about current LLM configuration."""
    if BACKEND == "groq" and GROQ_API_KEY:
        return {"backend": "groq", "model": MODEL_GROQ, "type": "cloud_free"}
    return {"backend": "ollama", "model": MODEL_OLLAMA, "type": "local"}
