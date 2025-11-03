from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str
    authentication_header_name: str = 'x-api-key'
    configurations_folder: str = 'configurations'
    aiod_url: str
    client_id: str
    client_secret: str
    keycloak_realm: str
    keycloak_url: str
    airedgio_endpoint: str
    airedgio_memory_filepath: str
    airedgio_translators_folder: str

    model_config = SettingsConfigDict(env_file='.env.dev')


settings = Settings()
