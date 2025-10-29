from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional
from dotenv import load_dotenv
import os

@dataclass
class Settings:
    SITE_URL: str
    PORTAL_URL: str
    SUCCESS_ORG_LABEL: str = "PREFEITURA MUNICIPAL DE JAPERI"
    CHECK_INTERVAL_HOURS: int = 3
    SLACK_WEBHOOK: Optional[str] = None
    TIMEZONE: str = "America/Sao_Paulo"
    DAILY_REPORT_HOUR: int = 23
    
    BASE_DIR: Path = Path.cwd() / "relatorio"
    FAIL_DIR: Path = BASE_DIR / "failures"
    DAILY_DIR: Path = BASE_DIR / "daily"
    MONTHLY_DIR: Path = BASE_DIR / "monthly"
    LOG_FILE: Path = BASE_DIR / "logs.jsonl"

    def __post_init__(self):
        if not self.SITE_URL or not self.PORTAL_URL:
            raise ValueError("SITE_URL e PORTAL_URL são obrigatórios")
        
        # Criar diretórios
        for d in (self.BASE_DIR, self.FAIL_DIR, self.DAILY_DIR, self.MONTHLY_DIR):
            d.mkdir(parents=True, exist_ok=True)
        
        # Validar timezone
        try:
            self.tz = ZoneInfo(self.TIMEZONE)
        except Exception as e:
            raise ValueError(f"Timezone inválido: {e}")

def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        SITE_URL=os.getenv("SITE_URL", "").strip(),
        PORTAL_URL=os.getenv("PORTAL_URL", "").strip(),
        SUCCESS_ORG_LABEL=os.getenv("SUCCESS_ORG_LABEL", "PREFEITURA MUNICIPAL DE JAPERI"),
        CHECK_INTERVAL_HOURS=int(os.getenv("CHECK_INTERVAL_HOURS", "3")),
        SLACK_WEBHOOK=os.getenv("SLACK_WEBHOOK", "").strip() or None,
        TIMEZONE=os.getenv("TIMEZONE", "America/Sao_Paulo"),
        DAILY_REPORT_HOUR=int(os.getenv("DAILY_REPORT_HOUR", "23"))
    )