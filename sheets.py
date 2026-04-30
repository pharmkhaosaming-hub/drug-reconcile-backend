"""
sheets.py — Google Sheets integration สำหรับเก็บข้อมูลคำขอยา
"""
import gspread
import json
import os
from google.oauth2.service_account import Credentials
from datetime import datetime
from cryptography.fernet import Fernet
import uuid
import logging

from config import settings

logger = logging.getLogger(__name__)

# Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet names
SHEET_INCOMING = "คำขอขาเข้า"
SHEET_OUTGOING = "คำขอขาออก"
SHEET_AUDIT_LOG = "Audit Log"

# Headers สำหรับแต่ละ sheet
INCOMING_HEADERS = [
    "Case ID", "วันที่-เวลา", "สถานะ",
    "รพ.ผู้ถาม", "ชื่อผู้ถาม", "วิชาชีพ", "เลขใบประกอบ", "เบอร์โทร",
    "ชื่อผู้ป่วย", "เลขบัตร (Masked)", "วันเกิดผู้ป่วย",
    "ประเภทคำถาม", "รายละเอียด",
    "PDPA Consent", "วัตถุประสงค์",
    "LINE User ID", "ตอบโดย", "วันที่ตอบ", "หมายเหตุ"
]

OUTGOING_HEADERS = [
    "Case ID", "วันที่-เวลา", "สถานะ",
    "ผู้ส่งคำถาม", "วิชาชีพ", "เลขใบประกอบ",
    "รพ./คลินิกปลายทาง", "เบอร์โทรปลายทาง",
    "ชื่อผู้ป่วย", "เลขบัตร (Masked)", "วันเกิดผู้ป่วย",
    "ประเภทคำถาม", "รายละเอียด",
    "PDPA Consent", "LINE User ID",
    "ผลการสอบถาม", "วันที่ได้รับผล"
]

AUDIT_HEADERS = [
    "Timestamp", "Action", "Case ID", "LINE User ID",
    "IP Address", "Details"
]


class SheetsManager:
    """จัดการ Google Sheets สำหรับระบบ Drug Reconciliation"""

    def __init__(self):
        self._client = None
        self._spreadsheet = None
        self._fernet = Fernet(settings.APP_SECRET_KEY.encode()
                              if len(settings.APP_SECRET_KEY) == 44
                              else Fernet.generate_key())

    def _get_client(self) -> gspread.Client:
        """Lazy-load Google Sheets client
        อ่าน credentials จาก env var GOOGLE_CREDENTIALS_JSON (สำหรับ Railway)
        หรือจาก file GOOGLE_SERVICE_ACCOUNT_FILE (สำหรับ local)
        """
        if self._client is None:
            if settings.GOOGLE_CREDENTIALS_JSON:
                # Railway: ใช้ JSON string จาก env var
                info = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            else:
                # Local: ใช้ไฟล์
                creds = Credentials.from_service_account_file(
                    settings.GOOGLE_SERVICE_ACCOUNT_FILE,
                    scopes=SCOPES
                )
            self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        """Lazy-load spreadsheet"""
        if self._spreadsheet is None:
            self._spreadsheet = self._get_client().open_by_key(
                settings.GOOGLE_SPREADSHEET_ID
            )
        return self._spreadsheet

    def _get_or_create_sheet(self, name: str, headers: list[str]) -> gspread.Worksheet:
        """ดึง worksheet หรือสร้างใหม่พร้อม header"""
        try:
            ws = self._get_spreadsheet().worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self._get_spreadsheet().add_worksheet(
                title=name, rows=1000, cols=len(headers)
            )
            ws.append_row(headers, value_input_option="USER_ENTERED")
            # Format header row
            ws.format("1:1", {
                "backgroundColor": {"red": 0.13, "green": 0.55, "blue": 0.13},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            })
        return ws

    def _mask_id_card(self, id_card: str) -> str:
        """Mask เลขบัตรประชาชน: แสดงแค่ 4 ตัวท้าย"""
        if len(id_card) >= 4:
            return "X" * (len(id_card) - 4) + id_card[-4:]
        return "X" * len(id_card)

    def _generate_case_id(self, prefix: str = "IN") -> str:
        """สร้าง Case ID เช่น IN-20240429-A1B2"""
        date_str = datetime.now().strftime("%Y%m%d")
        short_uuid = str(uuid.uuid4())[:4].upper()
        return f"{prefix}-{date_str}-{short_uuid}"

    def save_incoming_query(self, data: dict) -> str:
        """บันทึกคำขอขาเข้าลง Google Sheets"""
        ws = self._get_or_create_sheet(SHEET_INCOMING, INCOMING_HEADERS)
        case_id = self._generate_case_id("IN")
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        from models import ProfessionType, QueryType
        profession_label = ProfessionType.label(data.get("requester_profession", ""))
        query_label = QueryType.label(data.get("query_type", ""))
        masked_id = self._mask_id_card(data.get("patient_id_card", ""))
        patient_name = f"{data.get('patient_first_name', '')} {data.get('patient_last_name', '')}"

        row = [
            case_id,                                          # Case ID
            now,                                              # วันที่-เวลา
            "รอดำเนินการ",                                  # สถานะ
            data.get("requester_hospital", ""),               # รพ.ผู้ถาม
            data.get("requester_name", ""),                   # ชื่อผู้ถาม
            profession_label,                                 # วิชาชีพ
            data.get("requester_license_no", ""),             # เลขใบประกอบ
            data.get("requester_phone", ""),                  # เบอร์โทร
            patient_name,                                     # ชื่อผู้ป่วย
            masked_id,                                        # เลขบัตร (Masked)
            data.get("patient_dob", ""),                      # วันเกิด
            query_label,                                      # ประเภทคำถาม
            data.get("query_detail", ""),                     # รายละเอียด
            "ได้รับความยินยอมแล้ว",                         # PDPA Consent
            data.get("pdpa_purpose", "เพื่อประกอบการรักษา"), # วัตถุประสงค์
            data.get("line_user_id", ""),                     # LINE User ID
            "",                                               # ตอบโดย
            "",                                               # วันที่ตอบ
            "",                                               # หมายเหตุ
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(f"Saved incoming case: {case_id}")
        self._log_audit("SUBMIT_INCOMING", case_id, data.get("line_user_id", ""), "บันทึกคำขอขาเข้า")
        return case_id

    def save_outgoing_query(self, data: dict) -> str:
        """บันทึกคำขอขาออกลง Google Sheets"""
        ws = self._get_or_create_sheet(SHEET_OUTGOING, OUTGOING_HEADERS)
        case_id = self._generate_case_id("OUT")
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        from models import ProfessionType, QueryType
        profession_label = ProfessionType.label(data.get("our_staff_profession", ""))
        query_label = QueryType.label(data.get("query_type", ""))
        masked_id = self._mask_id_card(data.get("patient_id_card", ""))
        patient_name = f"{data.get('patient_first_name', '')} {data.get('patient_last_name', '')}"

        row = [
            case_id,
            now,
            "รอดำเนินการ",
            data.get("our_staff_name", ""),
            profession_label,
            data.get("our_staff_license_no", ""),
            data.get("target_hospital", ""),
            data.get("target_hospital_phone", ""),
            patient_name,
            masked_id,
            data.get("patient_dob", ""),
            query_label,
            data.get("query_detail", ""),
            "ได้รับความยินยอมแล้ว",
            data.get("line_user_id", ""),
            "",  # ผลการสอบถาม
            "",  # วันที่ได้รับผล
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(f"Saved outgoing case: {case_id}")
        self._log_audit("SUBMIT_OUTGOING", case_id, data.get("line_user_id", ""), "บันทึกคำขอขาออก")
        return case_id

    def _log_audit(self, action: str, case_id: str, line_user_id: str, detail: str):
        """บันทึก audit log ทุก action (PDPA compliance)"""
        try:
            ws = self._get_or_create_sheet(SHEET_AUDIT_LOG, AUDIT_HEADERS)
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            ws.append_row([now, action, case_id, line_user_id, "", detail])
        except Exception as e:
            logger.error(f"Audit log error: {e}")


# Singleton instance
sheets_manager = SheetsManager()
