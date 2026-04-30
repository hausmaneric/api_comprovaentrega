import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        default_data_dir = base_dir / "data"

        self.data_dir = Path(os.getenv("DATA_DIR", str(default_data_dir)))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        sqlite_path = os.getenv("SQLITE_PATH")
        if sqlite_path:
            self.sqlite_path = Path(sqlite_path)
        else:
            self.sqlite_path = self.data_dir / "comprova_entrega.db"
