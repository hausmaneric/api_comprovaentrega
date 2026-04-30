# ComprovaEntrega API

API inicial em FastAPI para multiempresa, clientes e entregas com prova obrigatoria.

## Conceitos base

- Cada empresa possui varios clientes.
- Cada entrega pertence a uma empresa e a um cliente.
- Finalizacao exige `photo_token`.
- Entrega finalizada nao pode ser alterada depois.
- O app mobile pode registrar offline e sincronizar depois.
- A sincronizacao pode enviar um lote de comprovante offline para a API depois.
- A API usa SQLite local por padrao nesta etapa.

## Railway

Arquivos incluidos para deploy:

- `Procfile`
- `railway.json`

Variaveis de ambiente recomendadas:

- `DATA_DIR=/data`
- `SQLITE_PATH=/data/comprova_entrega.db`

## Subir localmente

```bash
pip install -e .
uvicorn app.main:app --reload
```

O banco local sera criado em `backend/data/comprova_entrega.db`.

Para receber sincronizacao do app Flutter local:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Para o Railway, use um volume persistente montado em `/data` para nao perder o SQLite entre deploys.

## Endpoints iniciais

- `GET /health`
- `GET /companies`
- `GET /customers?company_id=cmp_1`
- `GET /deliveries?company_id=cmp_1&status=pending`
- `POST /deliveries`
- `POST /deliveries/{delivery_id}/finalize`
- `POST /sync/proofs`
- `GET /dashboard/{company_id}`

## Exemplo de sincronizacao offline

```json
{
  "company_id": "cmp_1",
  "delivery_id": "del_1",
  "device_id": "device-moto-g84",
  "queued_at": "2026-04-29T18:10:00Z",
  "proof": {
    "photo_token": "local-photo-001",
    "signed_by": "Carlos Eduardo",
    "latitude": -23.5505,
    "longitude": -46.6333,
    "delivered_at": "2026-04-29T18:06:00Z",
    "device_recorded_at": "2026-04-29T18:05:58Z",
    "offline_captured": true
  }
}
```
