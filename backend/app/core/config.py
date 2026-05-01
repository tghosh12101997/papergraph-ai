from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PaperGraph AI"
    app_version: str = "0.2.0"
    storage_dir: Path = Path("app/storage")
    base_uri: str = "https://example.org/papergraph/"

    # Optional Apache Jena Fuseki integration
    fuseki_enabled: bool = False
    fuseki_dataset_url: str = "http://localhost:3030/papergraph"

    # Optional local LLM through Ollama
    llm_enabled: bool = False
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_timeout_seconds: int = 120

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
