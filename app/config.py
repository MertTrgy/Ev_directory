from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'evdb-ingestion-service'
    log_level: str = 'INFO'
    cors_origins: str = 'http://localhost:5173'

    database_url: str = 'postgresql+psycopg://postgres:postgres@localhost:5432/evdb'

    evdb_data_url: str = 'http://host.docker.internal:3000/api/v1/vehicles/list'
    evdb_vehicle_detail_url_template: str | None = None
    evdb_api_key: str | None = None
    evdb_api_key_header: str = 'Authorization'
    evdb_timeout_seconds: int = 60
    requests_per_second: float = 1.0
    evdb_page_size: int = 100
    evdb_market: str = 'global'
    evdb_source_name: str = 'open-ev-data-api'
    evdb_fetch_vehicle_details: bool = True

    def cors_origins_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(',') if item.strip()]
        return origins or ['*']


settings = Settings()
