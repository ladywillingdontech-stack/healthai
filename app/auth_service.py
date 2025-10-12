"""
Firebase Authentication Service for Health AI Bot
Handles admin and doctor authentication with role-based access control
"""

import firebase_admin
from firebase_admin import auth, credentials
from typing import Optional, Dict, Any, List
import jwt
from datetime import datetime, timedelta
from app.config import settings
from app.models import UserRole, UserStatus, User, UserResponse

class AuthService:
    def __init__(self):
        """Initialize authentication service"""
        if not firebase_admin._apps:
            try:
                # Direct Firebase credentials (same as other services)
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
                
                print("🔧 Initializing Firebase Auth with direct credentials...")
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Auth initialized successfully!")
            except Exception as e:
                print(f"❌ Firebase Auth initialization failed: {e}")
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify Firebase ID token and return user info"""
        try:
            # Verify the token
            decoded_token = auth.verify_id_token(token)
            
            # Get user data
            user = auth.get_user(decoded_token['uid'])
            
            # Get custom claims
            custom_claims = decoded_token.get('role', 'user')
            
            return {
                'uid': user.uid,
                'email': user.email,
                'role': custom_claims,
                'verified': True
            }
        except Exception as e:
            print(f"❌ Token verification failed: {e}")
            return None
    
    def create_user(self, email: str, password: str, name: str, role: UserRole, permissions: List[str] = None) -> Optional[str]:
        """Create a new user with custom claims"""
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )
            
            # Set custom claims based on role
            claims = {'role': role.value}
            if permissions:
                claims['permissions'] = permissions
            
            auth.set_custom_user_claims(user.uid, claims)
            
            print(f"✅ Created {role.value} user: {email}")
            return user.uid
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return None
    
    def create_admin_user(self, email: str, password: str, name: str) -> Optional[str]:
        """Create an admin user with full permissions"""
        admin_permissions = [
            'view_all_patients',
            'view_all_emrs',
            'view_all_reports',
            'manage_users',
            'manage_settings',
            'export_data',
            'view_analytics'
        ]
        return self.create_user(email, password, name, UserRole.ADMIN, admin_permissions)
    
    def create_doctor_user(self, email: str, password: str, name: str) -> Optional[str]:
        """Create a doctor user with medical permissions"""
        doctor_permissions = [
            'view_assigned_patients',
            'view_patient_emrs',
            'create_emrs',
            'view_reports',
            'update_patient_info'
        ]
        return self.create_user(email, password, name, UserRole.DOCTOR, doctor_permissions)
    
    def create_nurse_user(self, email: str, password: str, name: str) -> Optional[str]:
        """Create a nurse user with limited permissions"""
        nurse_permissions = [
            'view_assigned_patients',
            'view_patient_emrs',
            'update_patient_vitals'
        ]
        return self.create_user(email, password, name, UserRole.NURSE, nurse_permissions)
    
    def update_user_role(self, uid: str, role: UserRole, permissions: List[str] = None) -> bool:
        """Update user's role and permissions"""
        try:
            claims = {'role': role.value}
            if permissions:
                claims['permissions'] = permissions
            
            auth.set_custom_user_claims(uid, claims)
            print(f"✅ Updated role for user {uid} to {role.value}")
            return True
        except Exception as e:
            print(f"❌ Error updating user role: {e}")
            return False
    
    def delete_user(self, uid: str) -> bool:
        """Delete a user"""
        try:
            auth.delete_user(uid)
            print(f"✅ Deleted user: {uid}")
            return True
        except Exception as e:
            print(f"❌ Error deleting user: {e}")
            return False
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        try:
            users = []
            for user in auth.list_users().iterate_users():
                users.append({
                    'uid': user.uid,
                    'email': user.email,
                    'display_name': user.display_name,
                    'email_verified': user.email_verified,
                    'disabled': user.disabled,
                    'custom_claims': user.custom_claims
                })
            return users
        except Exception as e:
            print(f"❌ Error listing users: {e}")
            return []
    
    def is_admin(self, token: str) -> bool:
        """Check if user is an admin"""
        user_info = self.verify_token(token)
        return user_info and user_info.get('role') == 'admin'
    
    def is_doctor(self, token: str) -> bool:
        """Check if user is a doctor"""
        user_info = self.verify_token(token)
        return user_info and user_info.get('role') == 'doctor'
    
    def is_nurse(self, token: str) -> bool:
        """Check if user is a nurse"""
        user_info = self.verify_token(token)
        return user_info and user_info.get('role') == 'nurse'
    
    def has_permission(self, token: str, permission: str) -> bool:
        """Check if user has specific permission"""
        user_info = self.verify_token(token)
        if not user_info:
            return False
        
        # Admins have all permissions
        if user_info.get('role') == 'admin':
            return True
        
        # Check specific permissions
        user_permissions = user_info.get('permissions', [])
        return permission in user_permissions
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            user = auth.get_user_by_email(email)
            return {
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name,
                'email_verified': user.email_verified,
                'disabled': user.disabled,
                'custom_claims': user.custom_claims
            }
        except Exception as e:
            print(f"❌ Error getting user by email: {e}")
            return None
    
    def disable_user(self, uid: str) -> bool:
        """Disable a user"""
        try:
            auth.update_user(uid, disabled=True)
            print(f"✅ Disabled user: {uid}")
            return True
        except Exception as e:
            print(f"❌ Error disabling user: {e}")
            return False
    
    def enable_user(self, uid: str) -> bool:
        """Enable a user"""
        try:
            auth.update_user(uid, disabled=False)
            print(f"✅ Enabled user: {uid}")
            return True
        except Exception as e:
            print(f"❌ Error enabling user: {e}")
            return False

# Global instance
auth_service = AuthService()
