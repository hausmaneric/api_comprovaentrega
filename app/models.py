from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"


class Company(BaseModel):
    id: str
    name: str
    legal_name: str


class Customer(BaseModel):
    id: str
    company_id: str
    name: str
    address: str


class DeliveryCreate(BaseModel):
    company_id: str
    customer_id: str
    driver_name: str
    address_snapshot: str
    requires_signature: bool = False
    external_reference: Optional[str] = None


class DeliveryProof(BaseModel):
    photo_token: str = Field(..., min_length=8)
    signed_by: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivered_at: datetime
    device_recorded_at: Optional[datetime] = None
    offline_captured: bool = False


class SyncUpload(BaseModel):
    company_id: str
    delivery_id: str
    proof: DeliveryProof
    device_id: str
    queued_at: datetime


class Delivery(BaseModel):
    id: str
    company_id: str
    customer_id: str
    driver_name: str
    address_snapshot: str
    status: DeliveryStatus
    requires_signature: bool
    immutable_record: bool = True
    proof: Optional[DeliveryProof] = None
    created_at: datetime
    external_reference: Optional[str] = None


class DashboardSummary(BaseModel):
    company_id: str
    pending: int
    in_transit: int
    delivered: int
    queued_offline_proofs: int
