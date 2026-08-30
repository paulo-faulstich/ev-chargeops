from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.identity.presentation.router import router as identity_router
from app.modules.ingestion.presentation.router import router as ingestion_router
from app.modules.sessions.presentation.router import router as sessions_router

app = FastAPI(title="EV ChargeOps API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(identity_router)
app.include_router(ingestion_router)
app.include_router(sessions_router)


@app.get("/health", tags=["platform"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ev-chargeops-api"}
