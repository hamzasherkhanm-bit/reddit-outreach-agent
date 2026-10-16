"""Loads config.yaml + .env into one settings object. Fails loudly if secrets are missing."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# Reddit credentials are intentionally NOT in this list: while Reddit's Data API
# registration is pending, the pipeline runs on the other sources and the Reddit
# source simply skips itself (see src/sources/__init__.py). The moment the
# REDDIT_* secrets are added, Reddit activates - no code changes needed.
REQUIRED_ENV = [
    "ANTHROPIC_API_KEY",
    "NOTION_TOKEN", "NOTION_DATABASE_ID",
    "RESEND_API_KEY", "EMAIL_FROM", "EMAIL_TO",
]


class Settings:
    def __init__(self, config_path: Path | None = None, check_env: bool = True):
        load_dotenv(REPO_ROOT / ".env")
        path = config_path or REPO_ROOT / "config.yaml"
        with open(path, "r", encoding="utf-8") as f:
            self.cfg: dict = yaml.safe_load(f)

        if check_env:
            missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
            if missing:
                raise RuntimeError(
                    f"Missing required environment variables: {', '.join(missing)}. "
                    "Copy .env.example to .env and fill them in (or set GitHub Secrets)."
                )

    # --- convenience accessors -------------------------------------------
    @property
    def reddit(self) -> dict:
        return self.cfg["sources"]["reddit"]

    @property
    def scoring(self) -> dict:
        return self.cfg["scoring"]

    @property
    def output(self) -> dict:
        return self.cfg["output"]

    @property
    def icp(self) -> dict:
        return self.cfg["icp"]

    def env(self, key: str, default: str = "") -> str:
        # .strip() guards against invisible newlines/spaces pasted into secrets
        return os.getenv(key, default).strip()

    def prompt(self, name: str) -> str:
        """Load a prompt template from prompts/<name>.txt."""
        return (REPO_ROOT / "prompts" / f"{name}.txt").read_text(encoding="utf-8")
