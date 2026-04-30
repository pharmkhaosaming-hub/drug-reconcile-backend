"""
line_handler.py — LINE Messaging API logic
ส่งข้อความแจ้งเตือนเภสัชกร + ตอบกลับผู้ใช้
"""
import logging
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, FlexMessage, FlexContainer,
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, FollowEvent
)

from config import settings

logger = logging.getLogger(__name__)

# LINE SDK setup
_configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)


def get_line_api() -> MessagingApi:
    return MessagingApi(ApiClient(_configuration))


# ─── Reply messages ──────────────────────────────────────────────────────────

def reply_text(reply_token: str, text: str):
    """ตอบกลับด้วยข้อความธรรมดา"""
    try:
        api = get_line_api()
        api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=text)]
        ))
    except Exception as e:
        logger.error(f"reply_text error: {e}")


def reply_welcome(reply_token: str):
    """ข้อความต้อนรับเมื่อ Follow"""
    msg = (
        "👋 สวัสดีครับ! ยินดีต้อนรับสู่ระบบ Drug Reconciliation\n\n"
        "📋 เมนูด้านล่างสามารถใช้งานได้ดังนี้:\n"
        "• 📥 รับคำขอยา — สำหรับ รพ.อื่นสอบถามยามาหาเรา\n"
        "• 📤 ส่งคำถาม — สำหรับเราถามไปยัง รพ./คลินิกอื่น\n"
        "• 🔍 ตรวจสอบสถานะ — ติดตามคำขอ\n"
        "• 🔒 ข้อมูล PDPA — นโยบายความเป็นส่วนตัว\n\n"
        "⚠️ ระบบนี้สำหรับบุคลากรทางการแพทย์เท่านั้น\n"
        "ข้อมูลผู้ป่วยได้รับการปกป้องตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562"
    )
    reply_text(reply_token, msg)


def reply_unknown(reply_token: str):
    """ตอบกลับเมื่อรับข้อความที่ไม่รู้จัก"""
    msg = (
        "กรุณาใช้เมนูด้านล่างเพื่อเข้าถึงบริการครับ 😊\n"
        "หากต้องการความช่วยเหลือ พิมพ์ 'help' หรือ 'ช่วยเหลือ'"
    )
    reply_text(reply_token, msg)


def reply_help(reply_token: str):
    """ข้อความช่วยเหลือ"""
    msg = (
        "📖 วิธีใช้งานระบบ Drug Reconciliation\n\n"
        "1️⃣ กด '📥 รับคำขอยา' เพื่อรับการสอบถามจาก รพ.อื่น\n"
        "   → กรอกข้อมูลผู้ถาม + ผู้ป่วย + ยืนยัน PDPA\n\n"
        "2️⃣ กด '📤 ส่งคำถาม' เพื่อถามไปยัง รพ.อื่น\n"
        "   → กรอกข้อมูลผู้ป่วยและเลือกปลายทาง\n\n"
        "3️⃣ ระบบจะแจ้งเตือนเภสัชกรโดยอัตโนมัติ\n\n"
        "📞 ติดต่อสอบถาม: " + settings.OUR_HOSPITAL_PHONE
    )
    reply_text(reply_token, msg)


# ─── Push notifications to pharmacist ──────────────────────────────────────

def notify_pharmacist_incoming(case_id: str, data: dict):
    """แจ้งเตือนเภสัชกรเมื่อมีคำขอขาเข้าใหม่"""
    pharmacist_ids = settings.get_pharmacist_ids()
    if not pharmacist_ids:
        logger.warning("No pharmacist LINE User IDs configured")
        return

    from models import ProfessionType, QueryType
    profession = ProfessionType.label(data.get("requester_profession", ""))
    query = QueryType.label(data.get("query_type", ""))
    patient_name = f"{data.get('patient_first_name', '')} {data.get('patient_last_name', '')}"

    text = (
        f"🔔 มีคำขอ Drug Reconciliation ใหม่!\n\n"
        f"📋 Case ID: {case_id}\n"
        f"🏥 จาก: {data.get('requester_hospital', '-')}\n"
        f"👤 ผู้ถาม: {data.get('requester_name', '-')} ({profession})\n"
        f"🪪 ใบประกอบ: {data.get('requester_license_no', '-')}\n"
        f"👦 ผู้ป่วย: {patient_name}\n"
        f"❓ ประเภท: {query}\n"
        f"✅ PDPA: ได้รับความยินยอมแล้ว\n\n"
        f"กรุณาตรวจสอบและตอบกลับใน Google Sheets"
    )
    _push_to_pharmacists(pharmacist_ids, text)


def notify_pharmacist_outgoing(case_id: str, data: dict):
    """แจ้งเตือนเภสัชกรเมื่อมีคำขอขาออกใหม่"""
    pharmacist_ids = settings.get_pharmacist_ids()
    if not pharmacist_ids:
        return

    from models import QueryType
    query = QueryType.label(data.get("query_type", ""))
    patient_name = f"{data.get('patient_first_name', '')} {data.get('patient_last_name', '')}"

    text = (
        f"📤 บันทึกคำขอขาออกใหม่\n\n"
        f"📋 Case ID: {case_id}\n"
        f"🏥 ปลายทาง: {data.get('target_hospital', '-')}\n"
        f"👦 ผู้ป่วย: {patient_name}\n"
        f"❓ ประเภท: {query}\n"
        f"👤 ส่งโดย: {data.get('our_staff_name', '-')}\n"
        f"✅ PDPA: ได้รับความยินยอมแล้ว"
    )
    _push_to_pharmacists(pharmacist_ids, text)


def _push_to_pharmacists(user_ids: list[str], text: str):
    """Push message ไปยัง pharmacist ทุกคน"""
    api = get_line_api()
    for uid in user_ids:
        try:
            api.push_message(PushMessageRequest(
                to=uid,
                messages=[TextMessage(text=text)]
            ))
        except Exception as e:
            logger.error(f"Push to {uid} failed: {e}")


# ─── Webhook event handlers ──────────────────────────────────────────────────

@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    """เมื่อผู้ใช้ Follow LINE OA"""
    reply_welcome(event.reply_token)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    """รับข้อความจากผู้ใช้"""
    text = event.message.text.strip().lower()
    help_keywords = ["help", "ช่วยเหลือ", "วิธีใช้", "?", "??"]
    if text in help_keywords:
        reply_help(event.reply_token)
    else:
        reply_unknown(event.reply_token)
