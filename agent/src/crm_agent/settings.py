from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    model: str = "openai:gpt-5.4-nano"
    gateway_url: str = "http://localhost:8001/mcp"
    gateway_secret: str
    es_url: str | None = None
    es_api_key: str | None = None
