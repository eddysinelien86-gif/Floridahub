from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    db_path: Path
    google_places_api_key: str
    telnyx_api_key: str
    telnyx_from_number: str
    telnyx_messaging_profile_id: str
    telnyx_public_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    sender_name: str
    company: str
    company_address: str
    pitch: str
    timezone: str
    send_window_start: int
    send_window_end: int
    daily_sms_cap: int
    daily_email_cap: int
    recontact_days: int
    admin_token: str
    dry_run: bool

    @property
    def sms_configured(self) -> bool:
        return bool(self.telnyx_api_key and self.telnyx_from_number)

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


def load_settings() -> Settings:
    default_db = Path(__file__).resolve().parents[1] / "outreach.db"
    return Settings(
        db_path=Path(_env("OUTREACH_DB_PATH") or default_db),
        google_places_api_key=_env("GOOGLE_PLACES_API_KEY"),
        telnyx_api_key=_env("TELNYX_API_KEY"),
        telnyx_from_number=_env("TELNYX_FROM_NUMBER"),
        telnyx_messaging_profile_id=_env("TELNYX_MESSAGING_PROFILE_ID"),
        telnyx_public_key=_env("TELNYX_PUBLIC_KEY"),
        smtp_host=_env("SMTP_HOST"),
        smtp_port=int(_env("SMTP_PORT", "587")),
        smtp_user=_env("SMTP_USER"),
        smtp_password=_env("SMTP_PASSWORD"),
        smtp_from=_env("SMTP_FROM"),
        sender_name=_env("OUTREACH_SENDER_NAME", "Your Name"),
        company=_env("OUTREACH_COMPANY", "Your Company"),
        company_address=_env("OUTREACH_COMPANY_ADDRESS"),
        pitch=_env(
            "OUTREACH_PITCH",
            "We send local contractors quote-ready homeowner appointments and only get paid after the job is completed.",
        ),
        timezone=_env("OUTREACH_TZ", "America/New_York"),
        send_window_start=int(_env("OUTREACH_SEND_START_HOUR", "9")),
        send_window_end=int(_env("OUTREACH_SEND_END_HOUR", "20")),
        daily_sms_cap=int(_env("OUTREACH_DAILY_SMS_CAP", "50")),
        daily_email_cap=int(_env("OUTREACH_DAILY_EMAIL_CAP", "100")),
        recontact_days=int(_env("OUTREACH_RECONTACT_DAYS", "30")),
        admin_token=_env("OUTREACH_ADMIN_TOKEN"),
        dry_run=_env("OUTREACH_DRY_RUN", "true").lower() not in {"0", "false", "no"},
    )
