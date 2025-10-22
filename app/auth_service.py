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
        self.initialized = False
        
        # Only initialize if we have the required environment variables
        if not all([
            settings.firebase_project_id,
            settings.firebase_private_key,
            settings.firebase_client_email
        ]):
            print("⚠️ Firebase environment variables not set - Auth service disabled")
            return
            
        if not firebase_admin._apps:
            try:
                # Use environment variables for Firebase credentials
                firebase_config = {
                    "type": "service_account",
                    "project_id": settings.firebase_project_id,
                    "private_key_id": settings.firebase_private_key_id,
                    "private_key": settings.firebase_private_key.replace('\\n', '\n'),
                    "client_email": settings.firebase_client_email,
                    "client_id": settings.firebase_client_id,
                    "auth_uri": settings.firebase_auth_uri,
                    "token_uri": settings.firebase_token_uri,
                    "auth_provider_x509_cert_url": settings.firebase_auth_provider_x509_cert_url,
                    "client_x509_cert_url": settings.firebase_client_x509_cert_url
                }
                
                print("🔧 Initializing Firebase Auth with environment credentials...")
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                print("✅ Firebase Auth initialized successfully!")
            except Exception as e:
                print(f"❌ Firebase Auth initialization failed: {e}")
                print("⚠️ Authentication will be disabled")
                self.initialized = False
        else:
            self.initialized = True
    
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
