from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class AlertLevel(str, Enum):
    NONE = "none"
    YELLOW = "yellow"
    RED = "red"

class ConversationPhase(str, Enum):
    ONBOARDING = "onboarding"
    DEMOGRAPHIC = "demographic"
    SYMPTOM = "symptom"
    WRAP_UP = "wrap_up"
    COMPLETED = "completed"

class UserRole(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class MessageSender(str, Enum):
    PATIENT = "patient"
    AI = "ai"
    DOCTOR = "doctor"

class User(BaseModel):
    id: Optional[str] = None
    email: str
    name: str
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    permissions: List[str] = []

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: UserRole
    permissions: List[str] = []

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login: Optional[datetime] = None
    permissions: List[str] = []

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse
    expires_in: int = 3600

# Patient Models
class Patient(BaseModel):
    id: Optional[str] = None
    name: str
    phone: str
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    medical_history: List[Dict[str, Any]] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class PatientCreate(BaseModel):
    name: str
    phone: str
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    medical_history: Optional[List[Dict[str, Any]]] = None

# Doctor Models
class Doctor(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    specialization: Optional[str] = None
    permissions: List[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DoctorCreate(BaseModel):
    name: str
    email: str
    password: str
    specialization: Optional[str] = None
    permissions: List[str] = []

class DoctorLogin(BaseModel):
    email: str
    password: str

class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    specialization: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

# Message Models
class Message(BaseModel):
    text: str
    timestamp: datetime
    sender: MessageSender

class MessageCreate(BaseModel):
    text: str
    sender: MessageSender

# Conversation Models
class Conversation(BaseModel):
    id: Optional[str] = None
    patient_id: str
    messages: List[Message] = []
    status: str = "active"
    phase: ConversationPhase = ConversationPhase.ONBOARDING
    completed_questions: List[str] = []
    patient_data: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ConversationCreate(BaseModel):
    patient_id: str
    initial_message: Optional[str] = ""

class ConversationUpdate(BaseModel):
    phase: Optional[ConversationPhase] = None
    patient_data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

# EMR Models
class Demographics(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    children: Optional[int] = None
    marital_status: Optional[str] = None
    occupation: Optional[str] = None
    address: Optional[str] = None

class Onboarding(BaseModel):
    marital_status: Optional[str] = None
    family_history: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None

class Symptom(BaseModel):
    symptom: str
    duration: Optional[str] = None
    severity: Optional[str] = None
    details: Optional[str] = None

class Alerts(BaseModel):
    status: str  # red, yellow, none
    reason: Optional[str] = None

class EMR(BaseModel):
    id: Optional[str] = None
    patient_id: str
    doctor_id: Optional[str] = None
    data: Dict[str, Any]
    pdf_url: Optional[str] = None
    status: str = "draft"
    alert_level: AlertLevel = AlertLevel.NONE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class EMRCreate(BaseModel):
    patient_id: str
    doctor_id: Optional[str] = None
    data: Dict[str, Any]
    pdf_url: Optional[str] = None
    alert_level: AlertLevel = AlertLevel.NONE

class EMRUpdate(BaseModel):
    data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    alert_level: Optional[AlertLevel] = None

# Voice Processing Models
class VoiceMessage(BaseModel):
    phone_number: str
    audio_url: Optional[str] = None
    text: Optional[str] = None  # For testing purposes

class VoiceResponse(BaseModel):
    success: bool
    message: str
    audio_url: Optional[str] = None

# Chroma DB Question Model
class ChromaQuestion(BaseModel):
    id: str
    question_text: str
    type: str  # onboarding, demographic, symptom
    condition: Optional[str] = None
    symptom: Optional[str] = None
    alert_flag: str = "none"  # red, yellow, none

# Alert Detection Models
class AlertDetection(BaseModel):
    status: str  # red, yellow, none
    reason: str
    confidence: float

# WhatsApp Webhook Models
class WhatsAppMessage(BaseModel):
    from_number: str
    message_type: str  # audio, text
    media_url: Optional[str] = None
    text: Optional[str] = None

# Doctor Note Models
class DoctorNoteCreate(BaseModel):
    emr_id: str
    note: str
    is_private: bool = True

class DoctorNoteResponse(BaseModel):
    id: str
    emr_id: str
    doctor_id: str
    note: str
    is_private: bool
    created_at: datetime

# Authentication Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# API Response Models
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None