"""
config.py — Application settings loaded from .env
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # LINE
    LINE_CHANNEL_ACCESS_TOKEN: str
    LINE_CHANNEL_SECRET: str
    LIFF_ID_INCOMING: str = ""
    LIFF_ID_OUTGOING: str = ""

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "./google_credentials.json"
    GOOGLE_SPREADSHEET_ID: str

    # App
    APP_SECRET_KEY: str
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Pharmacist notification
    PHARMACIST_LINE_USER_ID: str = ""
    PHARMACIST_LINE_USER_IDS: str = ""  # comma-separated

    # Hospital info
    OUR_HOSPITAL_NAME: str = "โรงพยาบาล/ร้านยาของเรา"
    OUR_HOSPITAL_PHONE: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    def get_pharmacist_ids(self) -> list[str]:
        """คืน list ของ LINE User ID เภสัชกรที่ต้องแจ้งเตือน"""
        ids = set()
        if self.PHARMACIST_LINE_USER_ID:
            ids.add(self.PHARMACIST_LINE_USER_ID)
        if self.PHARMACIST_LINE_USER_IDS:
            for uid in self.PHARMACIST_LINE_USER_IDS.split(","):
                uid = uid.strip()
                if uid:
                    ids.add(uid)
        return list(ids)


settings = Settings()
