from pydantic_settings import BaseSettings, SettingsConfigDict


# This is a configuration file for a FastAPI application using Pydantic for settings management. Read into .env file.
class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_EXPIRATION_IN_MIN: int
    JWT_REFRESH_EXPIRATION_IN_HOURS: int

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )


settings = Settings()  # type: ignore
