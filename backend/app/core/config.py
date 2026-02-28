from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "fastapi-counter"
    app_env: str = "dev"
    log_level: str = "INFO"
    uploads_dir: str = "app/storage/uploads"
    uploads_max_size_mb: int = 10
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = (
        r"^https?://("
        r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
        r"10\.\d+\.\d+\.\d+|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|"
        r"192\.168\.\d+\.\d+"
        r")(:\d+)?$"
    )
    genai_api_key: str = ""
    genai_base_url: str = "https://api.gen-api.ru/api/v1"
    genai_default_llm_network: str = "gemini-3-flash"
    genai_default_image_network: str = "flux-2"
    genai_images_dir: str = "app/storage/genai"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
