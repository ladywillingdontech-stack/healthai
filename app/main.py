from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, UploadFile, File, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uuid
import os
import openai
from datetime import datetime

from app.firestore_service import firestore_service
from app.models import *
from app.intelligent_conversation_engine import intelligent_conversation_engine
from app.voice_processing import voice_processor
from app.whatsapp_meta_service import whatsapp_service
from app.emr_generator import emr_generator
from app.urdu_transliteration_parser import UrduChromaDBSetup
from app.auth_service import auth_service
from app.reports_service import reports_service
from app.config import settings

# Create FastAPI app
app = FastAPI(
    title="Health AI Bot API",
    description="Healthcare intake system with AI-powered Urdu voice conversations using Firestore",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://your-frontend-domain.railway.app",  # Update this with your actual frontend URL
        "https://your-frontend-domain.netlify.app",  # If using Netlify
        "https://your-frontend-domain.vercel.app",   # If using Vercel
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Health AI Bot API is running", "version": "1.0.0"}

# Render health-check sends HEAD /. Ensure 200 instead of 405.
@app.head("/")
async def root_head() -> Response:
    return Response(status_code=200)

# Health check endpoint for Railway
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Health AI Bot API"
    }

# Production endpoints
@app.post("/voice-conversation", response_model=VoiceResponse)
async def voice_conversation(audio: UploadFile = File(...), patient_id: str = "default_patient"):
    """Complete voice conversation: Voice -> Text -> AI Response -> Voice"""
    try:
        # Save uploaded file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Step 1: Convert speech to text
            print(f"Converting speech to text from: {tmp_file_path}")
            text = await voice_processor.speech_to_text(tmp_file_path)
            print(f"Transcribed text: {text}")
            
            if not text:
                return VoiceResponse(
                    success=False,
                    message="Could not transcribe audio. Please try speaking more clearly.",
                    audio_url=None
                )
            
            # Step 2: Process conversation using the intelligent engine with Firestore
            print(f"Processing conversation for patient: {patient_id}")
            conversation_result = await intelligent_conversation_engine.process_patient_response(
                patient_text=text,
                patient_id=patient_id
            )
            
            updated_patient_data = conversation_result.get("patient_data", {})
            print(f"Updated patient data: {updated_patient_data.get('demographics', {})}")
            
            # Step 3: Generate AI response text
            response_text = conversation_result.get('response_text', 'I understand. Please tell me more about your symptoms.')
            print(f"AI Response: {response_text}")
            
            # Step 3.5: Check if EMR generation is needed
            action = conversation_result.get('action', 'continue_conversation')
            if action == 'generate_emr':
                print("🚨 Generating EMR for completed conversation...")
                try:
                    emr_result = await intelligent_conversation_engine.generate_emr(patient_id)
                    if emr_result:
                        print("✅ EMR generated successfully")
                    else:
                        print("❌ EMR generation failed")
                except Exception as e:
                    print(f"❌ EMR generation error: {e}")
            
            # Step 4: Convert response to speech
            print("Converting response to speech...")
            audio_file = voice_processor.text_to_speech(response_text)
            
            return VoiceResponse(
                success=True,
                message="Voice conversation completed successfully",
                audio_url=audio_file,
                response_text=response_text,
                patient_data=updated_patient_data
            )
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except Exception as e:
        print(f"Error in voice conversation: {e}")
        return VoiceResponse(
            success=False,
            message=f"Error processing voice conversation: {str(e)}",
            audio_url=None
        )

@app.post("/conversation")
async def conversation(patient_text: str, patient_id: str = "default_patient"):
    """Process text conversation"""
    try:
        result = await intelligent_conversation_engine.process_patient_response(
            patient_text=patient_text,
            patient_id=patient_id
        )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/generate-emr")
async def generate_emr(patient_id: str):
    """Generate EMR for patient"""
    try:
        emr_result = await intelligent_conversation_engine.generate_emr(patient_id)
        return {
            "success": emr_result,
            "message": "EMR generated successfully" if emr_result else "EMR generation failed"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Authentication endpoints
@app.post("/auth/login")
async def login(credentials: dict):
    """Login for doctors and admins"""
    try:
        username = credentials.get("username")
        password = credentials.get("password")
        
        # Simple hardcoded credentials for demo (in production, use proper authentication)
        valid_users = {
            "doctor": {"password": "doctor123", "role": "doctor", "name": "Dr. Sarah Ahmed"},
            "admin": {"password": "admin123", "role": "admin", "name": "Admin User"},
            "gynecologist": {"password": "gyne123", "role": "doctor", "name": "Dr. Fatima Khan"}
        }
        
        if username in valid_users and valid_users[username]["password"] == password:
            return {
                "success": True,
                "user": {
                    "username": username,
                    "role": valid_users[username]["role"],
                    "name": valid_users[username]["name"]
                },
                "message": "Login successful"
            }
        else:
            return {
                "success": False,
                "error": "Invalid credentials"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/auth/logout")
async def logout():
    """Logout endpoint"""
    return {
        "success": True,
        "message": "Logout successful"
    }

@app.get("/auth/verify")
async def verify_token():
    """Verify authentication token"""
    # For demo purposes, always return valid
    return {
        "success": True,
        "user": {
            "username": "demo_user",
            "role": "doctor",
            "name": "Demo User"
        }
    }

@app.post("/fix-emr-alert-levels")
async def fix_emr_alert_levels():
    """Fix EMRs that don't have alert levels"""
    try:
        # Get all patients
        patients_response = await firestore_service.get_all_patients()
        fixed_count = 0
        
        for patient in patients_response:
            patient_id = patient.get('patient_id', '')
            if patient_id:
                # Get EMRs for this patient
                emrs = await firestore_service.get_patient_emrs(patient_id)
                
                for emr in emrs:
                    # Check if EMR has alert level
                    if not emr.get('alert_level') or emr.get('alert_level') not in ['red', 'yellow', 'green']:
                        print(f"🔧 Fixing EMR for patient {patient_id} - missing alert level")
                        
                        # Generate assessment based on patient data
                        assessment = await intelligent_conversation_engine._generate_assessment(patient)
                        alert_level = assessment.get("alert_level", "yellow")
                        
                        # Update EMR with alert level
                        emr_id = emr.get('id') or f"{patient_id}_{emr.get('created_at', '')}"
                        await firestore_service.update_emr(emr_id, {
                            "alert_level": alert_level,
                            "assessment_summary": assessment.get("assessment_summary", "Standard gynecological consultation"),
                            "clinical_impression": assessment.get("clinical_impression", "Requires further evaluation")
                        })
                        
                        # Update patient data
                        await firestore_service.update_patient(patient_id, {
                            "alert_level": alert_level,
                            "assessment_summary": assessment.get("assessment_summary", "Standard gynecological consultation"),
                            "clinical_impression": assessment.get("clinical_impression", "Requires further evaluation")
                        })
                        
                        fixed_count += 1
                        print(f"✅ Fixed EMR for patient {patient_id} with alert level: {alert_level}")
        
        return {
            "success": True,
            "message": f"Fixed {fixed_count} EMRs with missing alert levels",
            "fixed_count": fixed_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fixed_count": 0
        }

@app.get("/get-all-emrs")
async def get_all_emrs():
    """Get all EMRs from all patients"""
    try:
        all_emrs = []
        
        # Get all patients first
        patients_response = await firestore_service.get_all_patients()
        
        # Get EMRs for each patient
        for patient in patients_response:
            patient_id = patient.get('patient_id', '')
            if patient_id:
                emrs = await firestore_service.get_patient_emrs(patient_id)
                if emrs:
                    # Add patient info to each EMR
                    for emr in emrs:
                        emr['patient_info'] = {
                            'patient_id': patient_id,
                            'name': patient.get('demographics', {}).get('name', 'Unknown'),
                            'age': patient.get('demographics', {}).get('age', 'Unknown'),
                            'phone': patient.get('demographics', {}).get('phone_number', 'Unknown')
                        }
                    all_emrs.extend(emrs)
        
        # Sort by creation date (newest first)
        all_emrs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return {
            "success": True,
            "emrs": all_emrs,
            "total_count": len(all_emrs)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "emrs": [],
            "total_count": 0
        }

# Patient management endpoints
@app.post("/patients")
async def create_patient(patient_data: dict):
    """Create a new patient"""
    try:
        patient_id = patient_data.get("patient_id", str(uuid.uuid4()))
        patient_data["patient_id"] = patient_id
        patient_data["created_at"] = datetime.now().isoformat()
        
        result = await firestore_service.create_patient(patient_data)
        return {"success": True, "patient_id": patient_id, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """Get patient by ID"""
    try:
        patient = await firestore_service.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return {"success": True, "patient": patient}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.put("/patients/{patient_id}")
async def update_patient(patient_id: str, patient_data: dict):
    """Update patient data"""
    try:
        patient_data["updated_at"] = datetime.now().isoformat()
        result = await firestore_service.update_patient(patient_id, patient_data)
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Conversation management endpoints
@app.post("/conversations")
async def create_conversation(conversation_data: dict):
    """Create a new conversation"""
    try:
        conversation_id = conversation_data.get("conversation_id", str(uuid.uuid4()))
        conversation_data["conversation_id"] = conversation_id
        conversation_data["created_at"] = datetime.now().isoformat()
        
        result = await firestore_service.create_conversation(conversation_data)
        return {"success": True, "conversation_id": conversation_id, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation by ID"""
    conversation = await firestore_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@app.post("/conversations/{conversation_id}/messages")
async def add_message(conversation_id: str, message_data: dict):
    """Add message to conversation"""
    try:
        message_id = str(uuid.uuid4())
        message_data["message_id"] = message_id
        message_data["timestamp"] = datetime.now().isoformat()
        
        result = await firestore_service.add_message_to_conversation(conversation_id, message_data)
        return {"success": True, "message_id": message_id, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# WhatsApp integration endpoints
@app.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """Verify WhatsApp webhook"""
    try:
        if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
            print("✅ Webhook verified successfully")
            return hub_challenge
        else:
            print("❌ Webhook verification failed")
            raise HTTPException(status_code=403, detail="Forbidden")
    except Exception as e:
        print(f"❌ Webhook verification error: {e}")
        raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Handle WhatsApp webhook"""
    try:
        body = await request.json()
        result = whatsapp_service.handle_webhook(body)
        return {"success": True, "result": result}
        
    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/whatsapp/send-message")
async def send_whatsapp_message(message_data: dict):
    """Send WhatsApp message"""
    try:
        result = whatsapp_service.send_message(
            phone_number=message_data["phone_number"],
            message=message_data["message"]
        )
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Authentication endpoints
@app.post("/auth/login")
async def login(credentials: dict):
    """User login"""
    try:
        result = await auth_service.login(credentials["email"], credentials["password"])
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/auth/register")
async def register(user_data: dict):
    """User registration"""
    try:
        result = await auth_service.register(user_data)
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Reports endpoints
@app.get("/reports/patients")
async def get_patient_reports():
    """Get patient reports"""
    try:
        reports = await reports_service.get_patient_reports()
        return {"success": True, "reports": reports}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/reports/conversations")
async def get_conversation_reports():
    """Get conversation reports"""
    try:
        reports = await reports_service.get_conversation_reports()
        return {"success": True, "reports": reports}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Setup endpoints
@app.post("/setup/chroma")
async def setup_chroma():
    """Setup ChromaDB for Urdu text processing"""
    try:
        setup = UrduChromaDBSetup()
        result = await setup.setup_chroma_db()
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
