from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "PaperGraph AI"
    app_version: str = "0.1.0"
    storage_dir: Path = Path("backend/app/storage")
    base_uri: str = "https://example.org/papergraph/"

    # Optional Apache Jena Fuseki integration
    fuseki_enabled: bool = False
    fuseki_dataset_url: str = "http://localhost:3030/papergraph"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
