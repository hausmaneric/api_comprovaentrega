from datetime import datetime

from .models import (
    Company,
    Customer,
    DashboardSummary,
    Delivery,
    DeliveryCreate,
    DeliveryProof,
    DeliveryStatus,
    SyncUpload,
)


class InMemoryRepository:
    def __init__(self) -> None:
        now = datetime.utcnow()
        self.companies = [
            Company(id="cmp_1", name="Aurora", legal_name="Aurora Distribuicao Ltda"),
            Company(id="cmp_2", name="Log Mais", legal_name="Log Mais Solucoes SA"),
        ]
        self.customers = [
            Customer(
                id="cus_1",
                company_id="cmp_1",
                name="Mercado Bom Vizinho",
                address="Rua das Mangueiras, 220 - Centro",
            ),
            Customer(
                id="cus_2",
                company_id="cmp_1",
                name="Farmacia Central",
                address="Av. Brasil, 810 - Jardim Novo",
            ),
            Customer(
                id="cus_3",
                company_id="cmp_2",
                name="Padaria Pao Quente",
                address="Rua Minas Gerais, 55 - Vila Rica",
            ),
        ]
        self.deliveries = [
            Delivery(
                id="del_1",
                company_id="cmp_1",
                customer_id="cus_1",
                driver_name="Mateus",
                address_snapshot="Rua das Mangueiras, 220 - Centro",
                status=DeliveryStatus.PENDING,
                requires_signature=False,
                created_at=now,
                external_reference="NF-20314",
            ),
            Delivery(
                id="del_2",
                company_id="cmp_1",
                customer_id="cus_2",
                driver_name="Sara",
                address_snapshot="Av. Brasil, 810 - Jardim Novo",
                status=DeliveryStatus.IN_TRANSIT,
                requires_signature=True,
                created_at=now,
                external_reference="NF-20319",
            ),
            Delivery(
                id="del_3",
                company_id="cmp_2",
                customer_id="cus_3",
                driver_name="Joao",
                address_snapshot="Rua Minas Gerais, 55 - Vila Rica",
                status=DeliveryStatus.DELIVERED,
                requires_signature=True,
                created_at=now,
                external_reference="NF-77801",
                proof=DeliveryProof(
                    photo_token="photo_tok_77801",
                    signed_by="Paulo Cesar",
                    latitude=-22.9071,
                    longitude=-47.0632,
                    delivered_at=now,
                    offline_captured=False,
                ),
            ),
        ]
        self.sync_uploads: list[SyncUpload] = []

    def list_companies(self) -> list[Company]:
        return self.companies

    def list_customers(self, company_id: str | None = None) -> list[Customer]:
        if company_id is None:
            return self.customers
        return [item for item in self.customers if item.company_id == company_id]

    def list_deliveries(
        self,
        company_id: str | None = None,
        status: DeliveryStatus | None = None,
    ) -> list[Delivery]:
        items = self.deliveries
        if company_id is not None:
            items = [item for item in items if item.company_id == company_id]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def create_delivery(self, payload: DeliveryCreate) -> Delivery:
        delivery = Delivery(
            id=f"del_{len(self.deliveries) + 1}",
            company_id=payload.company_id,
            customer_id=payload.customer_id,
            driver_name=payload.driver_name,
            address_snapshot=payload.address_snapshot,
            status=DeliveryStatus.PENDING,
            requires_signature=payload.requires_signature,
            created_at=datetime.utcnow(),
            external_reference=payload.external_reference,
        )
        self.deliveries.append(delivery)
        return delivery

    def finalize_delivery(self, delivery_id: str, proof: DeliveryProof) -> Delivery:
        for index, item in enumerate(self.deliveries):
            if item.id != delivery_id:
                continue
            if item.status == DeliveryStatus.DELIVERED:
                raise ValueError("Entrega ja foi finalizada e nao pode ser alterada.")
            updated = item.model_copy(
                update={
                    "status": DeliveryStatus.DELIVERED,
                    "proof": proof,
                }
            )
            self.deliveries[index] = updated
            return updated
        raise LookupError("Entrega nao encontrada.")

    def register_sync_upload(self, payload: SyncUpload) -> Delivery:
        self.sync_uploads.append(payload)
        return self.finalize_delivery(payload.delivery_id, payload.proof)

    def dashboard_summary(self, company_id: str) -> DashboardSummary:
        items = [item for item in self.deliveries if item.company_id == company_id]
        return DashboardSummary(
            company_id=company_id,
            pending=sum(item.status == DeliveryStatus.PENDING for item in items),
            in_transit=sum(item.status == DeliveryStatus.IN_TRANSIT for item in items),
            delivered=sum(item.status == DeliveryStatus.DELIVERED for item in items),
            queued_offline_proofs=sum(
                upload.company_id == company_id and upload.proof.offline_captured
                for upload in self.sync_uploads
            ),
        )
