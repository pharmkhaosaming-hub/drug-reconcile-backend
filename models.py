"""
models.py — Pydantic data models สำหรับ Drug Reconciliation System
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class QueryType(str, Enum):
    DRUG_RECONCILIATION = "drug_reconciliation"
    ALLERGY_HISTORY = "allergy_history"
    DRUG_INTERACTION = "drug_interaction"
    MEDICATION_LIST = "medication_list"
    OTHER = "other"

    @classmethod
    def label(cls, value: str) -> str:
        labels = {
            "drug_reconciliation": "Drug Reconciliation (สอบถามยาเดิม)",
            "allergy_history": "ประวัติแพ้ยา",
            "drug_interaction": "Drug Interaction",
            "medication_list": "รายการยาทั้งหมด",
            "other": "อื่นๆ",
        }
        return labels.get(value, value)


class ProfessionType(str, Enum):
    PHARMACIST = "pharmacist"
    PHYSICIAN = "physician"
    NURSE = "nurse"
    DENTIST = "dentist"
    OTHER = "other"

    @classmethod
    def label(cls, value: str) -> str:
        labels = {
            "pharmacist": "เภสัชกร",
            "physician": "แพทย์",
            "nurse": "พยาบาล",
            "dentist": "ทันตแพทย์",
            "other": "อื่นๆ",
        }
        return labels.get(value, value)


# ─── Incoming Request (รพ.อื่นสอบถามมาหาเรา) ───────────────────────────────

class IncomingQueryForm(BaseModel):
    """แบบฟอร์มขาเข้า: ผู้ถามจาก รพ.อื่นส่งคำถามมาหาเรา"""

    # ข้อมูลผู้ถาม
    requester_hospital: str = Field(..., min_length=2, description="โรงพยาบาลที่สังกัด")
    requester_name: str = Field(..., min_length=2, description="ชื่อ-นามสกุลผู้ถาม")
    requester_profession: ProfessionType = Field(..., description="ตำแหน่งวิชาชีพ")
    requester_profession_other: Optional[str] = Field(None, description="ระบุวิชาชีพอื่น")
    requester_license_no: str = Field(..., min_length=3, description="เลขใบประกอบวิชาชีพ")
    requester_phone: Optional[str] = Field(None, description="เบอร์โทรศัพท์ผู้ถาม")

    # ข้อมูลผู้ป่วย
    patient_first_name: str = Field(..., min_length=1, description="ชื่อผู้ป่วย")
    patient_last_name: str = Field(..., min_length=1, description="นามสกุลผู้ป่วย")
    patient_id_card: str = Field(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก")
    patient_dob: Optional[str] = Field(None, description="วันเกิดผู้ป่วย (DD/MM/YYYY)")

    # ประเภทคำถาม
    query_type: QueryType = Field(..., description="ประเภทข้อมูลที่ต้องการ")
    query_detail: Optional[str] = Field(None, description="รายละเอียดเพิ่มเติม")

    # PDPA
    pdpa_consent: bool = Field(..., description="ยืนยันได้รับความยินยอมจากผู้ป่วยแล้ว")
    pdpa_purpose: str = Field(
        default="เพื่อประกอบการรักษาพยาบาล",
        description="วัตถุประสงค์การใช้ข้อมูล"
    )

    # LINE metadata (ไม่ได้กรอกโดยผู้ใช้)
    line_user_id: Optional[str] = Field(None, description="LINE User ID ของผู้ถาม")

    @field_validator("patient_id_card")
    @classmethod
    def validate_thai_id(cls, v: str) -> str:
        v = v.strip().replace("-", "").replace(" ", "")
        if not v.isdigit() or len(v) != 13:
            raise ValueError("เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก")
        # Thai ID checksum
        total = sum(int(v[i]) * (13 - i) for i in range(12))
        check = (11 - (total % 11)) % 10
        if check != int(v[12]):
            raise ValueError("เลขบัตรประชาชนไม่ถูกต้อง")
        return v

    @field_validator("pdpa_consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("ต้องได้รับความยินยอม PDPA จากผู้ป่วยก่อนส่งข้อมูล")
        return v


# ─── Outgoing Request (เราส่งคำถามไป รพ./คลินิกอื่น) ────────────────────────

class OutgoingQueryForm(BaseModel):
    """แบบฟอร์มขาออก: เราถามไปยัง รพ./คลินิกอื่น"""

    # ข้อมูลผู้ถาม (ของเรา)
    our_staff_name: str = Field(..., min_length=2, description="ชื่อ-นามสกุลผู้ส่งคำถาม")
    our_staff_profession: ProfessionType = Field(..., description="ตำแหน่งวิชาชีพ")
    our_staff_license_no: str = Field(..., min_length=3, description="เลขใบประกอบวิชาชีพ")

    # ปลายทาง
    target_hospital: str = Field(..., min_length=2, description="โรงพยาบาล/คลินิกที่ต้องการสอบถาม")
    target_hospital_phone: Optional[str] = Field(None, description="เบอร์โทรปลายทาง")

    # ข้อมูลผู้ป่วย
    patient_first_name: str = Field(..., min_length=1, description="ชื่อผู้ป่วย")
    patient_last_name: str = Field(..., min_length=1, description="นามสกุลผู้ป่วย")
    patient_id_card: str = Field(..., min_length=13, max_length=13, description="เลขบัตรประชาชน 13 หลัก")
    patient_dob: Optional[str] = Field(None, description="วันเกิดผู้ป่วย")

    # ประเภทคำถาม
    query_type: QueryType = Field(..., description="ประเภทข้อมูลที่ต้องการ")
    query_detail: Optional[str] = Field(None, description="รายละเอียดเพิ่มเติม")

    # PDPA
    pdpa_consent: bool = Field(..., description="ยืนยันได้รับความยินยอมจากผู้ป่วยแล้ว")

    # LINE metadata
    line_user_id: Optional[str] = Field(None, description="LINE User ID ของผู้ส่ง")

    @field_validator("patient_id_card")
    @classmethod
    def validate_thai_id(cls, v: str) -> str:
        v = v.strip().replace("-", "").replace(" ", "")
        if not v.isdigit() or len(v) != 13:
            raise ValueError("เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก")
        total = sum(int(v[i]) * (13 - i) for i in range(12))
        check = (11 - (total % 11)) % 10
        if check != int(v[12]):
            raise ValueError("เลขบัตรประชาชนไม่ถูกต้อง")
        return v

    @field_validator("pdpa_consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("ต้องได้รับความยินยอม PDPA ก่อนส่งคำถาม")
        return v


# ─── Response models ───────────────────────────────────────────────────────────

class SubmitResponse(BaseModel):
    success: bool
    case_id: str
    message: str


class CaseStatus(BaseModel):
    case_id: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]
    created_at: str
    updated_at: str
    query_type: str
