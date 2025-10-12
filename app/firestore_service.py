"""
Firestore Service for Health AI Bot
Handles all database operations using Google Firestore
"""

import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import os
from app.config import settings

class FirestoreService:
    def __init__(self):
        """Initialize Firestore service"""
        # Initialize Firebase Admin SDK
        if not firebase_admin._apps:
            try:
                # Direct Firebase credentials (from your env file)
                firebase_config = {
                    "type": "service_account",
                    "project_id": "health-ai-7e5e0",
                    "private_key_id": "421286dea6c4142e6a1825c352a4908beda55c79",
                    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCbLi7Gz0srdaK8\nls/9qQtYnr+KXPh9iaWZkxcIzvrEZDn3z8t6HrfOgWIS83mQvK3uF7RhQ+uE3ADg\nlwvyLO26PMNG29wDjNmGU8yLsif1xg+Cseeqdw3SxtH2VKbRCSTEzOdBe/7AtG90\ndJ3+Q7Q102otyoR98gs3M/EMvCl803d/fx3fvJFYVWeivLqIqNiEc0p1+YNdNe2x\n4xmJhIlwiQQx0jVWC0Z6dXW0I6alIJw9DAnEgcx35EMAO17Hyk2sLnc46BgbH5G8\nG0WXbPzrjBWyG3gRh4tsbdKVX4E1simt5s4X9jk1jeF3YNXeJq8aEjbThur1KthQ\nn2mpUnoxAgMBAAECggEAEMo1km+Bomv3FcY62ScDTMKEVov08N7wlXC2Pc7oj/uI\n0Bi3WyOxXyey56UDQqyUzwgujUA5iSWlTKeFyd1K7WsUn86QUVavKcWtrHG0Dsyw\nB0PeHRyw2LIyq8nV8L5iBY8RTbhaRG8MCMLIs2bk5oFU4YEiG7RmupbP88D0u4YZ\n/i4pfMDSiPhIWAbpmUDgArRFKojZ3WJK2VTygN9nV8fjfadf2zfVUNF3r4IW5EsL\nJY3elxYsPikrZ+Sk66I58f9UwhzmjET8RdPHKCNe+mYW5hctMUjr3/ghuQwjsdy+\nbTuRvF+4+Q1s8i2Y08FbvoskMfLSz9H+YGiJtr6ohwKBgQDMTJO2HB9ol1z7fWLN\nGXkgyfi+VSAyf7MrUxb61aBxDuHru2VzIIWJXRfNb2wvR+zEiJU9Z4AjMm23+iI2\nDSA7ll6ZejeqX305Pxrtlgq4PhOIodbkijMgUi3sx5T4PPav2HqrnOhFBfmmT9aZ\nnM1op4oIfAtM1G1bzFAMiKXCvwKBgQDCc3jYOMr7QnExi7AYPAFhzntMVd8YkoHa\nsv8s6mv9sdjY/4M58PAiBeOCQ9J8psCohuIs38SUyGx0tb5LcbN0Xg5YW8kRscJA\nzKqsC0f1AbiAr46xAhHVLtcPT02tIO9n1Mjj7B5QY42KQJTzpUHHN9a1VuYHGqPJ\nOJlk/OUvDwKBgHnFfxnCA3qdFeAU6Yokj81adXhFVw6ijRHa0cyq/pnE7CZNKXgI\nv2+T3Hcn3c0EyvyOCJ50Da1tBnbtkeyzwC2kQDis33ceuY4grhVFJJiS76O2C1dn\nhHfUY+lJQOMBu2wu1VdrDArwN9DIr7oZ+1lQ23aZMUcXKyPXUTNXU64TAoGBAIBj\nzf62QQ/1pteX7AWUWTVDKJYWfN+0nJjSZzo47mTr8MoWq4auV1+fk8CHF4vGbp7X\nsK8AcMPsMfA9sBAQWvUSxVYCBJjyTdiLSoWeTTywjiopwIWPYEbqToWFTzxo6qoc\nDSiw1rMtiF8olTDqhKwNam8BmZBHPq21+VJ8yLZxAoGBAMmtA04I+z98ClGNLGFv\ndaD1gfgdMkQf6aikF4tNOD4Q8wFnh3zZKYC54tx5kRw9/FSL0XLFn+Na8o7Pccb/\nfSbpoh7MpyPqp/w9kBkUYGhg6n5iLOkPC1W8B5JVy7P+L9ZH34n+MwkbamjdLRS1\nVS1PCTHyrQi5VMnYi6HLoJAY\n-----END PRIVATE KEY-----\n",
                    "client_email": "firebase-adminsdk-fbsvc@health-ai-7e5e0.iam.gserviceaccount.com",
                    "client_id": "109131766928724539318",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40health-ai-7e5e0.iam.gserviceaccount.com"
                }
                
                print("🔧 Initializing Firebase with direct credentials...")
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': "health-ai-7e5e0.appspot.com"
                })
                self.db = firestore.client()
                print("✅ Firebase initialized successfully!")
                
            except Exception as e:
                print(f"⚠️ Firestore initialization failed: {e}")
                print("⚠️ Running in development mode without Firestore")
                self.db = None
        else:
            self.db = firestore.client()
    
    # Patient Management
    async def create_patient(self, patient_data: Dict) -> str:
        """Create a new patient document"""
        try:
            if self.db is None:
                print("⚠️ Firestore not initialized, cannot create patient")
                raise Exception("Firestore not initialized")
            
            patient_id = patient_data.get('patient_id')
            if not patient_id:
                raise Exception("patient_id is required")
            
            # Use patient_id as the document ID
            doc_ref = self.db.collection('patients').document(patient_id)
            patient_data['created_at'] = datetime.utcnow()
            patient_data['updated_at'] = datetime.utcnow()
            patient_data['id'] = patient_id
            doc_ref.set(patient_data)
            return patient_id
        except Exception as e:
            print(f"Error creating patient: {e}")
            raise e
    
    async def get_patient(self, patient_id: str) -> Optional[Dict]:
        """Get patient by ID"""
        try:
            if self.db is None:
                print("⚠️ Firestore not initialized, returning None")
                return None
            
            print(f"🔍 Looking for patient document: {patient_id}")
            doc = self.db.collection('patients').document(patient_id).get()
            print(f"📄 Document exists: {doc.exists}")
            
            if doc.exists:
                patient_data = doc.to_dict()
                print(f"✅ Found patient: {patient_data.get('demographics', {}).get('name', 'Unknown')}")
                return patient_data
            else:
                print(f"❌ Patient document not found: {patient_id}")
                return None
                
        except Exception as e:
            print(f"Error getting patient: {e}")
            return None
    
    async def get_all_patients(self) -> List[Dict]:
        """Get all patients"""
        try:
            if self.db is None:
                print("⚠️ Firestore not initialized, returning empty list")
                return []
            
            docs = self.db.collection('patients').get()
            patients = []
            for doc in docs:
                patient_data = doc.to_dict()
                patient_data['patient_id'] = doc.id
                patients.append(patient_data)
            
            print(f"📋 Retrieved {len(patients)} patients")
            return patients
            
        except Exception as e:
            print(f"Error getting all patients: {e}")
            return []
    
    async def update_patient(self, patient_id: str, update_data: Dict) -> bool:
        """Update patient data"""
        try:
            update_data['updated_at'] = datetime.utcnow()
            self.db.collection('patients').document(patient_id).update(update_data)
            return True
        except Exception as e:
            print(f"Error updating patient: {e}")
            return False
    
    async def list_patients(self, limit: int = 100) -> List[Dict]:
        """List all patients"""
        try:
            docs = self.db.collection('patients').limit(limit).get()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error listing patients: {e}")
            return []
    
    # Conversation Management
    async def create_conversation(self, patient_id: str, initial_message: str = "") -> str:
        """Create a new conversation"""
        try:
            conversation_data = {
                'patient_id': patient_id,
                'messages': [{
                    'text': initial_message,
                    'timestamp': datetime.utcnow(),
                    'sender': 'patient'
                }] if initial_message else [],
                'status': 'active',
                'phase': 'onboarding',
                'completed_questions': [],
                'patient_data': {},
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            doc_ref = self.db.collection('conversations').document()
            conversation_data['id'] = doc_ref.id
            doc_ref.set(conversation_data)
            return doc_ref.id
        except Exception as e:
            print(f"Error creating conversation: {e}")
            raise e
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation by ID"""
        try:
            doc = self.db.collection('conversations').document(conversation_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Error getting conversation: {e}")
            return None
    
    async def get_active_conversation(self, patient_id: str) -> Optional[Dict]:
        """Get active conversation for patient"""
        try:
            docs = self.db.collection('conversations').where('patient_id', '==', patient_id).where('status', '==', 'active').limit(1).get()
            return docs[0].to_dict() if docs else None
        except Exception as e:
            print(f"Error getting active conversation: {e}")
            return None
    
    async def add_message(self, conversation_id: str, message: str, sender: str) -> bool:
        """Add message to conversation"""
        try:
            conversation_ref = self.db.collection('conversations').document(conversation_id)
            conversation_ref.update({
                'messages': firestore.ArrayUnion([{
                    'text': message,
                    'timestamp': datetime.utcnow(),
                    'sender': sender
                }]),
                'updated_at': datetime.utcnow()
            })
            return True
        except Exception as e:
            print(f"Error adding message: {e}")
            return False
    
    async def update_conversation_phase(self, conversation_id: str, phase: str, patient_data: Dict = None) -> bool:
        """Update conversation phase and patient data"""
        try:
            update_data = {
                'phase': phase,
                'updated_at': datetime.utcnow()
            }
            if patient_data:
                update_data['patient_data'] = patient_data
            
            self.db.collection('conversations').document(conversation_id).update(update_data)
            return True
        except Exception as e:
            print(f"Error updating conversation phase: {e}")
            return False
    
    async def complete_conversation(self, conversation_id: str) -> bool:
        """Mark conversation as completed"""
        try:
            self.db.collection('conversations').document(conversation_id).update({
                'status': 'completed',
                'updated_at': datetime.utcnow()
            })
            return True
        except Exception as e:
            print(f"Error completing conversation: {e}")
            return False
    
    # EMR Management
    async def create_emr(self, patient_id: str, emr_data: Dict, doctor_id: str = None, pdf_url: str = None) -> str:
        """Create a new EMR"""
        try:
            # Add metadata to the EMR data directly
            emr_data['patient_id'] = patient_id
            emr_data['doctor_id'] = doctor_id
            emr_data['pdf_url'] = pdf_url
            emr_data['status'] = 'draft'
            emr_data['alert_level'] = emr_data.get('alert_level', 'none')
            emr_data['created_at'] = datetime.utcnow()
            emr_data['updated_at'] = datetime.utcnow()
            
            doc_ref = self.db.collection('emrs').document()
            emr_data['id'] = doc_ref.id
            doc_ref.set(emr_data)
            return doc_ref.id
        except Exception as e:
            print(f"Error creating EMR: {e}")
            raise e
    
    async def get_emr(self, emr_id: str) -> Optional[Dict]:
        """Get EMR by ID"""
        try:
            doc = self.db.collection('emrs').document(emr_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Error getting EMR: {e}")
            return None
    
    async def get_patient_emrs(self, patient_id: str) -> List[Dict]:
        """Get all EMRs for a patient"""
        try:
            # First get all EMRs for the patient without ordering
            docs = self.db.collection('emrs').where('patient_id', '==', patient_id).get()
            emrs = [doc.to_dict() for doc in docs]
            
            # Sort in Python to avoid Firestore index requirement
            emrs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return emrs
        except Exception as e:
            print(f"Error getting patient EMRs: {e}")
            return []
    
    async def get_emrs_by_alert(self, alert_level: str) -> List[Dict]:
        """Get EMRs by alert level"""
        try:
            # Get EMRs without ordering to avoid index requirement
            docs = self.db.collection('emrs').where('alert_level', '==', alert_level).get()
            emrs = [doc.to_dict() for doc in docs]
            
            # Sort in Python
            emrs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return emrs
        except Exception as e:
            print(f"Error getting EMRs by alert: {e}")
            return []
    
    async def update_emr(self, emr_id: str, update_data: Dict) -> bool:
        """Update EMR"""
        try:
            update_data['updated_at'] = datetime.utcnow()
            self.db.collection('emrs').document(emr_id).update(update_data)
            return True
        except Exception as e:
            print(f"Error updating EMR: {e}")
            return False
    
    # Doctor Management
    async def create_doctor(self, doctor_data: Dict) -> str:
        """Create a new doctor"""
        try:
            doctor_data['created_at'] = datetime.utcnow()
            doctor_data['updated_at'] = datetime.utcnow()
            doc_ref = self.db.collection('doctors').document()
            doctor_data['id'] = doc_ref.id
            doc_ref.set(doctor_data)
            return doc_ref.id
        except Exception as e:
            print(f"Error creating doctor: {e}")
            raise e
    
    async def get_doctor(self, doctor_id: str) -> Optional[Dict]:
        """Get doctor by ID"""
        try:
            doc = self.db.collection('doctors').document(doctor_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Error getting doctor: {e}")
            return None
    
    async def get_doctor_by_email(self, email: str) -> Optional[Dict]:
        """Get doctor by email"""
        try:
            docs = self.db.collection('doctors').where('email', '==', email).limit(1).get()
            return docs[0].to_dict() if docs else None
        except Exception as e:
            print(f"Error getting doctor by email: {e}")
            return None
    
    async def list_doctors(self) -> List[Dict]:
        """List all doctors"""
        try:
            docs = self.db.collection('doctors').get()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error listing doctors: {e}")
            return []
    
    # Real-time Updates
    def listen_to_patient_updates(self, patient_id: str, callback):
        """Listen to real-time patient updates"""
        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == 'MODIFIED':
                    callback(change.document.to_dict())
        
        self.db.collection('patients').document(patient_id).on_snapshot(on_snapshot)
    
    def listen_to_emr_updates(self, patient_id: str, callback):
        """Listen to real-time EMR updates"""
        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == 'ADDED' or change.type.name == 'MODIFIED':
                    callback(change.document.to_dict())
        
        self.db.collection('emrs').where('patient_id', '==', patient_id).on_snapshot(on_snapshot)
    
    def listen_to_new_emrs(self, callback):
        """Listen to new EMRs being created"""
        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == 'ADDED':
                    callback(change.document.to_dict())
        
        self.db.collection('emrs').order_by('created_at', direction=firestore.Query.DESCENDING).on_snapshot(on_snapshot)

# Global instance
firestore_service = FirestoreService()
