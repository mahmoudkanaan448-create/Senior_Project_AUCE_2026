"""
AI-Powered Network Traffic Analyzer & Anomaly Detector.

FastAPI backend entry point: creates the app, enables CORS, registers
routes, initializes the database on startup, and seeds a default admin.
Run: python main.py  (or uvicorn main:app --reload --port 8000)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.database import init_db, SessionLocal
from database.queries import get_user_by_username, create_user
from api.authentication import hash_password
from api.routes import router
from config import APP_VERSION

app = FastAPI(
    title="AI Network Traffic Analyzer & Anomaly Detector",
    description="AI-Powered NDR Platform – Senior Project AUCE 2026",
    version=APP_VERSION,
)

_cors = os.getenv("AINDR_CORS_ORIGINS", "*")
_origins = [x.strip() for x in _cors.split(",") if x.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        from api.rate_limit import allow
        ip = request.client.host if request.client else "unknown"
        if not allow(ip):
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    return await call_next(request)


app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()
    _seed_admin()
    try:
        from ops.bootstrap import bootstrap
        bootstrap()
    except Exception:
        pass


def _seed_admin():
    """Create default admin user if none exists (change password after first login)."""
    import os
    db = SessionLocal()
    try:
        if not get_user_by_username(db, "admin"):
            from ops.company import company_mode, min_password_len
            pw = os.getenv("AINDR_ADMIN_PASSWORD") or ""
            if company_mode() and (not pw or len(pw) < min_password_len()):
                raise RuntimeError(
                    "Company mode is on: set AINDR_ADMIN_PASSWORD in .env "
                    f"(min {min_password_len()} chars) before first start."
                )
            if not pw:
                pw = "admin123"
            create_user(
                db,
                full_name="System Administrator",
                username="admin",
                email="admin@auce.edu.lb",
                password_hash=hash_password(pw),
                role="Administrator",
            )
    finally:
        db.close()


if __name__ == "__main__":
    import os
    import uvicorn
    reload = os.getenv("AINDR_RELOAD", "0") in ("1", "true", "True", "yes")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload)
