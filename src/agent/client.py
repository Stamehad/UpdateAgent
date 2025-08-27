import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

def make_client(project_root: Path) -> OpenAI:
    load_dotenv(project_root / ".env")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set (.env or env var).")
    return OpenAI(api_key=api_key)