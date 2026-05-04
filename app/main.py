from fastapi import FastAPI, HTTPException, Query

from .models import (
    AuthSessionResponse,
    DashboardSummary,
    Delivery,
    DeliveryCreate,
    DeliveryProof,
    DeliveryStatus,
    LoginRequest,
    RegisterCompanyUserRequest,
    SyncUpload,
)
from .repository_sqlite import SqliteRepository
from .settings import Settings

app = FastAPI(
    title="ComprovaEntrega API",
    version="0.1.0",
    description="API inicial para prova de entrega multiempresa e offline-first.",
)
settings = Settings()
repo = SqliteRepository(str(settings.sqlite_path))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/companies")
def list_companies():
    return repo.list_companies()


@app.post("/auth/register", response_model=AuthSessionResponse)
def register_company_and_user(payload: RegisterCompanyUserRequest):
    try:
        return repo.register_company_with_owner(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/auth/login", response_model=AuthSessionResponse)
def login(payload: LoginRequest):
    try:
        return repo.login(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/customers")
def list_customers(company_id: str | None = Query(default=None)):
    return repo.list_customers(company_id=company_id)


@app.get("/deliveries", response_model=list[Delivery])
def list_deliveries(
    company_id: str | None = Query(default=None),
    status: DeliveryStatus | None = Query(default=None),
):
    return repo.list_deliveries(company_id=company_id, status=status)


@app.post("/deliveries", response_model=Delivery)
def create_delivery(payload: DeliveryCreate):
    return repo.create_delivery(payload)


@app.post("/deliveries/{delivery_id}/finalize", response_model=Delivery)
def finalize_delivery(delivery_id: str, proof: DeliveryProof):
    if not proof.photo_token:
        raise HTTPException(status_code=400, detail="Foto obrigatoria.")
    try:
        return repo.finalize_delivery(delivery_id, proof)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/sync/proofs", response_model=Delivery)
def sync_proof(payload: SyncUpload):
    if not payload.proof.photo_token:
        raise HTTPException(status_code=400, detail="Foto obrigatoria.")
    try:
        return repo.register_sync_upload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/dashboard/{company_id}", response_model=DashboardSummary)
def dashboard(company_id: str):
    return repo.dashboard_summary(company_id)
