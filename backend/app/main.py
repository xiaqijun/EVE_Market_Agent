from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.logging import setup_logging, TraceIdMiddleware

setup_logging()

app = FastAPI(title="EVE Market Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.middleware.sanitizer import sanitizer_middleware
app.middleware("http")(sanitizer_middleware)
app.add_middleware(TraceIdMiddleware)

from app.api.auth import router as auth_router
from app.api.market import router as market_router
from app.api.opportunities import router as opportunities_router
from app.api.trades import router as trades_router
from app.api.portfolio import router as portfolio_router
from app.api.users import router as users_router
from app.api.notifications import router as notifications_router
from app.api.websocket import router as ws_router
from app.api.admin import router as admin_router
from app.api.system_status import router as system_router

app.include_router(auth_router)
app.include_router(market_router)
app.include_router(opportunities_router)
app.include_router(trades_router)
app.include_router(portfolio_router)
app.include_router(users_router)
app.include_router(notifications_router)
app.include_router(ws_router)
app.include_router(admin_router)
app.include_router(system_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
