from fastapi import FastAPI

app = FastAPI(title="EV ChargeOps API", version="0.1.0")


@app.get("/health", tags=["platform"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ev-chargeops-api"}
