"""
main.py — FastAPI Application หลัก
Drug Reconciliation LINE OA Backend
"""
import logging
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import WebhookPayload

from config import settings
from models import IncomingQueryForm, OutgoingQueryForm, SubmitResponse
from sheets import sheets_manager
from line_handler import handler, notify_pharmacist_incoming, notify_pharmacist_outgoing

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Drug Reconciliation LINE OA API",
    description="Backend API สำหรับระบบ Drug Reconciliation ผ่าน LINE Official Account",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI (ปิดใน production)
    redoc_url="/redoc",
)

# CORS — อนุญาตให้ LIFF (line.me domain) เรียก API ได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://liff.line.me",
        "https://miniapp.line.me",
        "http://localhost:3000",  # dev
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ─── Health Check ────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Drug Reconciliation API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


# ─── LINE Webhook ────────────────────────────────────────────────────────────
@app.post("/webhook", tags=["LINE"])
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(..., alias="X-Line-Signature"),
):
    """
    รับ Webhook events จาก LINE Platform
    ต้อง verify signature ทุกครั้งเพื่อความปลอดภัย
    """
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        logger.warning("Invalid LINE signature received")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

    return JSONResponse(content={"status": "ok"})


# ─── LIFF API — ส่งฟอร์มขาเข้า ───────────────────────────────────────────────
@app.post("/api/submit-incoming", response_model=SubmitResponse, tags=["Forms"])
async def submit_incoming(form: IncomingQueryForm):
    """
    รับข้อมูลจาก LIFF Form ขาเข้า
    (บุคลากรทางการแพทย์จาก รพ.อื่นสอบถามยาของผู้ป่วยมาหาเรา)
    """
    logger.info(f"Incoming query from: {form.requester_hospital} / {form.requester_name}")
    try:
        case_id = sheets_manager.save_incoming_query(form.model_dump())
        notify_pharmacist_incoming(case_id, form.model_dump())
        return SubmitResponse(
            success=True,
            case_id=case_id,
            message=f"บันทึกคำขอเรียบร้อยแล้ว\nCase ID: {case_id}\nเภสัชกรจะติดต่อกลับโดยเร็วที่สุด"
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Submit incoming error: {e}")
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")


# ─── LIFF API — ส่งฟอร์มขาออก ───────────────────────────────────────────────
@app.post("/api/submit-outgoing", response_model=SubmitResponse, tags=["Forms"])
async def submit_outgoing(form: OutgoingQueryForm):
    """
    รับข้อมูลจาก LIFF Form ขาออก
    (บุคลากรของเราถามไปยัง รพ./คลินิกอื่น)
    """
    logger.info(f"Outgoing query to: {form.target_hospital} by {form.our_staff_name}")
    try:
        case_id = sheets_manager.save_outgoing_query(form.model_dump())
        notify_pharmacist_outgoing(case_id, form.model_dump())
        return SubmitResponse(
            success=True,
            case_id=case_id,
            message=f"บันทึกคำขอขาออกแล้ว\nCase ID: {case_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Submit outgoing error: {e}")
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")


# ─── LIFF Config endpoint ────────────────────────────────────────────────────
@app.get("/api/liff-config", tags=["Config"])
async def get_liff_config():
    """คืนค่า LIFF IDs สำหรับ frontend"""
    return {
        "liff_id_incoming": settings.LIFF_ID_INCOMING,
        "liff_id_outgoing": settings.LIFF_ID_OUTGOING,
        "hospital_name": settings.OUR_HOSPITAL_NAME,
    }


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
