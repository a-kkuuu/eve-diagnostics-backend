import time
import logging
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.routers import auth, centres, tests_catalogue, bookings, payments
from app.database import get_db
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="EVE Diagnostics Backend")

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    
    logger.info(f"method={request.method} path={request.url.path} status={response.status_code} duration_ms={duration_ms:.1f}")
    return response

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests_catalogue.router)
app.include_router(bookings.router)
app.include_router(payments.router)

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"healthcheck_failed error={str(e)}")
        return JSONResponse(status_code=503, content={"status": "error"})
