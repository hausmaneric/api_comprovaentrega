from .models import SyncUpload


sync_example = SyncUpload.model_validate(
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
            "offline_captured": True,
        },
    }
)
