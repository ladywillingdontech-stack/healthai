import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = "your_openai_key_here"
    openai_embedding_model: str = "text-embedding-ada-002"
    openai_chat_model: str = "gpt-4"
    
    # ElevenLabs Configuration
    elevenlabs_api_key: str = "your_elevenlabs_key_here"
    elevenlabs_voice_id: str = "your_voice_id_here"
    
    # Meta WhatsApp Business API Configuration
    whatsapp_access_token: str = "your_whatsapp_access_token_here"
    whatsapp_phone_number_id: str = "your_phone_number_id_here"
    whatsapp_verify_token: str = "your_verify_token_here"
    whatsapp_api_version: str = "v18.0"
    
    # Firebase Configuration
    firebase_project_id: str = "your_firebase_project_id"
    firebase_private_key_id: str = "your_private_key_id"
    firebase_private_key: str = "your_private_key"
    firebase_client_email: str = "your_client_email"
    firebase_client_id: str = "your_client_id"
    firebase_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    firebase_token_uri: str = "https://oauth2.googleapis.com/token"
    firebase_auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    firebase_client_x509_cert_url: str = "your_client_cert_url"
    
    # Database Configuration - Firestore
    firebase_project_id: str = "your_firebase_project_id"
    firebase_service_account_path: str = "firebase-service-account.json"
    chroma_db_path: str = "./chroma_db"
    
    # Security
    secret_key: str = "your_secret_key_here_change_this_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Application Configuration
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"


settings = Settings()
