import json
import sqlite3
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from .models import (
    AuthSessionResponse,
    Company,
    Customer,
    DashboardSummary,
    Delivery,
    DeliveryCreate,
    DeliveryProof,
    DeliveryStatus,
    LoginRequest,
    RegisterCompanyUserRequest,
    SyncUpload,
    User,
)


class SqliteRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_if_empty()

    def list_companies(self) -> list[Company]:
        with self._connect() as conn:
            rows = conn.execute(
                "select id, name, legal_name, document from companies order by name"
            ).fetchall()
        return [
            Company(id=row[0], name=row[1], legal_name=row[2], document=row[3])
            for row in rows
        ]

    def register_company_with_owner(
        self, payload: RegisterCompanyUserRequest
    ) -> AuthSessionResponse:
        stamp = int(datetime.utcnow().timestamp())
        company_id = f"cmp_{stamp}"
        user_id = f"usr_{stamp}"
        password_hash = self._hash_password(payload.password)

        with self._connect() as conn:
            existing = conn.execute(
                "select id from users where email = ?",
                (payload.user_email.lower(),),
            ).fetchone()
            if existing is not None:
                raise ValueError("Ja existe um usuario com este email.")

            conn.execute(
                """
                insert into companies (id, name, legal_name, document)
                values (?, ?, ?, ?)
                """,
                (
                    company_id,
                    payload.company_name,
                    payload.company_legal_name,
                    payload.company_document,
                ),
            )
            conn.execute(
                """
                insert into users (id, company_id, name, email, password_hash, role)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    company_id,
                    payload.user_name,
                    payload.user_email.lower(),
                    password_hash,
                    "owner",
                ),
            )

        company = Company(
            id=company_id,
            name=payload.company_name,
            legal_name=payload.company_legal_name,
            document=payload.company_document,
        )
        user = User(
            id=user_id,
            company_id=company_id,
            name=payload.user_name,
            email=payload.user_email.lower(),
            role="owner",
        )
        return AuthSessionResponse(
            company=company,
            user=user,
            access_token=self._issue_token(user_id, company_id),
        )

    def login(self, payload: LoginRequest) -> AuthSessionResponse:
        with self._connect() as conn:
            row = conn.execute(
                """
                select u.id, u.company_id, u.name, u.email, u.password_hash, u.role,
                       c.id, c.name, c.legal_name, c.document
                from users u
                join companies c on c.id = u.company_id
                where u.email = ?
                """,
                (payload.email.lower(),),
            ).fetchone()

        if row is None:
            raise LookupError("Usuario nao encontrado.")

        if row[4] != self._hash_password(payload.password):
            raise ValueError("Senha invalida.")

        user = User(
            id=row[0],
            company_id=row[1],
            name=row[2],
            email=row[3],
            role=row[5],
        )
        company = Company(
            id=row[6],
            name=row[7],
            legal_name=row[8],
            document=row[9],
        )
        return AuthSessionResponse(
            company=company,
            user=user,
            access_token=self._issue_token(user.id, company.id),
        )

    def list_customers(self, company_id: str | None = None) -> list[Customer]:
        query = "select id, company_id, name, address from customers"
        params: tuple[str, ...] = ()
        if company_id is not None:
            query += " where company_id = ?"
            params = (company_id,)
        query += " order by name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            Customer(id=row[0], company_id=row[1], name=row[2], address=row[3])
            for row in rows
        ]

    def list_deliveries(
        self,
        company_id: str | None = None,
        status: DeliveryStatus | None = None,
    ) -> list[Delivery]:
        query = """
            select id, company_id, customer_id, driver_name, address_snapshot,
                   status, requires_signature, immutable_record, proof_json,
                   created_at, external_reference
            from deliveries
            where 1 = 1
        """
        params: list[str] = []
        if company_id is not None:
            query += " and company_id = ?"
            params.append(company_id)
        if status is not None:
            query += " and status = ?"
            params.append(status.value)
        query += " order by created_at desc"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._delivery_from_row(row) for row in rows]

    def create_delivery(self, payload: DeliveryCreate) -> Delivery:
        delivery = Delivery(
            id=f"del_{int(datetime.utcnow().timestamp())}",
            company_id=payload.company_id,
            customer_id=payload.customer_id,
            driver_name=payload.driver_name,
            address_snapshot=payload.address_snapshot,
            status=DeliveryStatus.PENDING,
            requires_signature=payload.requires_signature,
            created_at=datetime.utcnow(),
            external_reference=payload.external_reference,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into deliveries (
                    id, company_id, customer_id, driver_name, address_snapshot,
                    status, requires_signature, immutable_record, proof_json,
                    created_at, external_reference
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._delivery_to_row(delivery),
            )
        return delivery

    def finalize_delivery(self, delivery_id: str, proof: DeliveryProof) -> Delivery:
        current = self._get_delivery(delivery_id)
        if current.status == DeliveryStatus.DELIVERED:
            raise ValueError("Entrega ja foi finalizada e nao pode ser alterada.")

        updated = current.model_copy(
            update={"status": DeliveryStatus.DELIVERED, "proof": proof}
        )
        with self._connect() as conn:
            conn.execute(
                """
                update deliveries
                set status = ?, proof_json = ?
                where id = ?
                """,
                (updated.status.value, self._proof_json(updated.proof), delivery_id),
            )
        return updated

    def register_sync_upload(self, payload: SyncUpload) -> Delivery:
        with self._connect() as conn:
            conn.execute(
                """
                insert into sync_uploads (
                    company_id, delivery_id, device_id, queued_at, proof_json
                ) values (?, ?, ?, ?, ?)
                """,
                (
                    payload.company_id,
                    payload.delivery_id,
                    payload.device_id,
                    payload.queued_at.isoformat(),
                    self._proof_json(payload.proof),
                ),
            )
        return self.finalize_delivery(payload.delivery_id, payload.proof)

    def dashboard_summary(self, company_id: str) -> DashboardSummary:
        items = self.list_deliveries(company_id=company_id)
        with self._connect() as conn:
            queued_offline_proofs = conn.execute(
                """
                select count(*)
                from sync_uploads
                where company_id = ?
                """,
                (company_id,),
            ).fetchone()[0]
        return DashboardSummary(
            company_id=company_id,
            pending=sum(item.status == DeliveryStatus.PENDING for item in items),
            in_transit=sum(item.status == DeliveryStatus.IN_TRANSIT for item in items),
            delivered=sum(item.status == DeliveryStatus.DELIVERED for item in items),
            queued_offline_proofs=queued_offline_proofs,
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists companies (
                    id text primary key,
                    name text not null,
                    legal_name text not null,
                    document text
                )
                """
            )
            conn.execute(
                """
                create table if not exists users (
                    id text primary key,
                    company_id text not null,
                    name text not null,
                    email text not null unique,
                    password_hash text not null,
                    role text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists customers (
                    id text primary key,
                    company_id text not null,
                    name text not null,
                    address text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists deliveries (
                    id text primary key,
                    company_id text not null,
                    customer_id text not null,
                    driver_name text not null,
                    address_snapshot text not null,
                    status text not null,
                    requires_signature integer not null,
                    immutable_record integer not null,
                    proof_json text,
                    created_at text not null,
                    external_reference text
                )
                """
            )
            conn.execute(
                """
                create table if not exists sync_uploads (
                    id integer primary key autoincrement,
                    company_id text not null,
                    delivery_id text not null,
                    device_id text not null,
                    queued_at text not null,
                    proof_json text not null
                )
                """
            )

    def _seed_if_empty(self) -> None:
        with self._connect() as conn:
            count = conn.execute("select count(*) from companies").fetchone()[0]
            if count:
                return

            now = datetime.utcnow().isoformat()
            conn.executemany(
                "insert into companies (id, name, legal_name, document) values (?, ?, ?, ?)",
                [
                    ("cmp_1", "Aurora", "Aurora Distribuicao Ltda", "12.345.678/0001-90"),
                    ("cmp_2", "Log Mais", "Log Mais Solucoes SA", "98.765.432/0001-12"),
                ],
            )
            conn.executemany(
                """
                insert into users (id, company_id, name, email, password_hash, role)
                values (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "usr_1",
                        "cmp_1",
                        "Sara Gestora",
                        "sara@aurora.com",
                        self._hash_password("123456"),
                        "owner",
                    ),
                    (
                        "usr_2",
                        "cmp_2",
                        "Joao Operador",
                        "joao@logmais.com",
                        self._hash_password("123456"),
                        "owner",
                    ),
                ],
            )
            conn.executemany(
                "insert into customers (id, company_id, name, address) values (?, ?, ?, ?)",
                [
                    ("cus_1", "cmp_1", "Mercado Bom Vizinho", "Rua das Mangueiras, 220 - Centro"),
                    ("cus_2", "cmp_1", "Farmacia Central", "Av. Brasil, 810 - Jardim Novo"),
                    ("cus_3", "cmp_2", "Padaria Pao Quente", "Rua Minas Gerais, 55 - Vila Rica"),
                ],
            )
            conn.executemany(
                """
                insert into deliveries (
                    id, company_id, customer_id, driver_name, address_snapshot,
                    status, requires_signature, immutable_record, proof_json,
                    created_at, external_reference
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "del_1",
                        "cmp_1",
                        "cus_1",
                        "Mateus",
                        "Rua das Mangueiras, 220 - Centro",
                        "pending",
                        0,
                        1,
                        None,
                        now,
                        "NF-20314",
                    ),
                    (
                        "del_2",
                        "cmp_1",
                        "cus_2",
                        "Sara",
                        "Av. Brasil, 810 - Jardim Novo",
                        "in_transit",
                        1,
                        1,
                        None,
                        now,
                        "NF-20319",
                    ),
                ],
            )

    def _get_delivery(self, delivery_id: str) -> Delivery:
        with self._connect() as conn:
            row = conn.execute(
                """
                select id, company_id, customer_id, driver_name, address_snapshot,
                       status, requires_signature, immutable_record, proof_json,
                       created_at, external_reference
                from deliveries
                where id = ?
                """,
                (delivery_id,),
            ).fetchone()
        if row is None:
            raise LookupError("Entrega nao encontrada.")
        return self._delivery_from_row(row)

    def _delivery_from_row(self, row: tuple) -> Delivery:
        proof = None
        if row[8]:
            proof = DeliveryProof.model_validate(json.loads(row[8]))
        return Delivery(
            id=row[0],
            company_id=row[1],
            customer_id=row[2],
            driver_name=row[3],
            address_snapshot=row[4],
            status=DeliveryStatus(row[5]),
            requires_signature=bool(row[6]),
            immutable_record=bool(row[7]),
            proof=proof,
            created_at=datetime.fromisoformat(row[9]),
            external_reference=row[10],
        )

    def _delivery_to_row(self, delivery: Delivery) -> tuple:
        return (
            delivery.id,
            delivery.company_id,
            delivery.customer_id,
            delivery.driver_name,
            delivery.address_snapshot,
            delivery.status.value,
            int(delivery.requires_signature),
            int(delivery.immutable_record),
            self._proof_json(delivery.proof),
            delivery.created_at.isoformat(),
            delivery.external_reference,
        )

    def _proof_json(self, proof: DeliveryProof | None) -> str | None:
        if proof is None:
            return None
        return json.dumps(proof.model_dump(mode="json"))

    def _hash_password(self, password: str) -> str:
        return sha256(password.encode("utf-8")).hexdigest()

    def _issue_token(self, user_id: str, company_id: str) -> str:
        raw = f"{user_id}:{company_id}:{datetime.utcnow().isoformat()}"
        return sha256(raw.encode("utf-8")).hexdigest()
