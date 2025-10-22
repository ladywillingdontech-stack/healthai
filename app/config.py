import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-ada-002"
    openai_chat_model: str = "gpt-4"
    
    # ElevenLabs Configuration
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    
    # Meta WhatsApp Business API Configuration
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_api_version: str = "v18.0"
    
    # Firebase Configuration
    firebase_project_id: str = ""
    firebase_private_key_id: str = ""
    firebase_private_key: str = ""
    firebase_client_email: str = ""
    firebase_client_id: str = ""
    firebase_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    firebase_token_uri: str = "https://oauth2.googleapis.com/token"
    firebase_auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    firebase_client_x509_cert_url: str = ""
    
    # Database Configuration
    firebase_service_account_path: str = "firebase-service-account.json"
    chroma_db_path: str = "/tmp/chroma_db"
    
    # Security
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Application Configuration
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
