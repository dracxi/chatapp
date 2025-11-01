from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    database_url: str = "sqlite:///./chat_app.db"
    
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    bcrypt_rounds: int = 12
    password_min_length: int = 8
    password_max_length: int = 128
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Chat Application API"
    api_description: str = "A real-time chat application"
    api_version: str = "1.0.0"
    
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    debug: bool = True

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()