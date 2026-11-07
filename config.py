import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = BASE_DIR / "data" / "bot.db"

def _admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise SystemExit(f"ADMIN_IDS содержит не число: {part}")
    return ids


ADMIN_IDS = _admin_ids()

CATEGORIES: dict[str, str] = {
    "consult": "Консультация",
    "order": "Заказ",
    "repair": "Ремонт",
    "other": "Другое",
}

STATUSES: dict[str, str] = {
    "new": "Новая",
    "in_progress": "В работе",
    "done": "Выполнена",
    "rejected": "Отклонена",
}
