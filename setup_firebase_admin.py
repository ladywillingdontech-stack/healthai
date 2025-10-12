#!/usr/bin/env python3
"""
Firebase Admin Setup Script for Health AI Bot
Creates admin and doctor users with proper roles and permissions
"""

import firebase_admin
from firebase_admin import credentials, auth
import json
import sys
from app.models import UserRole

def setup_firebase_admin():
    """Initialize Firebase Admin SDK"""
    try:
        # Initialize with service account
        cred = credentials.Certificate('firebase-service-account.json')
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin SDK initialized")
        return True
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return False

def create_admin_user(email: str, password: str, name: str) -> bool:
    """Create an admin user with full permissions"""
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # Set admin custom claims
        auth.set_custom_user_claims(user.uid, {
            'role': 'admin',
            'permissions': [
                'view_all_patients',
                'view_all_emrs',
                'view_all_reports',
                'manage_users',
                'manage_settings',
                'export_data',
                'view_analytics'
            ]
        })
        
        print(f"✅ Created admin user: {email}")
        return True
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

def create_doctor_user(email: str, password: str, name: str) -> bool:
    """Create a doctor user with medical permissions"""
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # Set doctor custom claims
        auth.set_custom_user_claims(user.uid, {
            'role': 'doctor',
            'permissions': [
                'view_assigned_patients',
                'view_patient_emrs',
                'create_emrs',
                'view_reports',
                'update_patient_info'
            ]
        })
        
        print(f"✅ Created doctor user: {email}")
        return True
    except Exception as e:
        print(f"❌ Error creating doctor user: {e}")
        return False

def create_nurse_user(email: str, password: str, name: str) -> bool:
    """Create a nurse user with limited permissions"""
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # Set nurse custom claims
        auth.set_custom_user_claims(user.uid, {
            'role': 'nurse',
            'permissions': [
                'view_assigned_patients',
                'view_patient_emrs',
                'update_patient_vitals'
            ]
        })
        
        print(f"✅ Created nurse user: {email}")
        return True
    except Exception as e:
        print(f"❌ Error creating nurse user: {e}")
        return False

def main():
    """Main function"""
    print("🏥 Health AI Bot - Firebase Admin Setup")
    print("=" * 50)
    
    # Initialize Firebase
    if not setup_firebase_admin():
        return False
    
    # Create users
    users_to_create = [
        # Admin users
        {"email": "admin@hospital.com", "password": "AdminPassword123!", "name": "Hospital Admin", "role": "admin"},
        {"email": "superadmin@hospital.com", "password": "SuperAdmin123!", "name": "Super Admin", "role": "admin"},
        
        # Doctor users
        {"email": "doctor1@hospital.com", "password": "DoctorPassword123!", "name": "Dr. Ahmed Khan", "role": "doctor"},
        {"email": "doctor2@hospital.com", "password": "DoctorPassword123!", "name": "Dr. Fatima Ali", "role": "doctor"},
        {"email": "doctor3@hospital.com", "password": "DoctorPassword123!", "name": "Dr. Muhammad Hassan", "role": "doctor"},
        
        # Nurse users
        {"email": "nurse1@hospital.com", "password": "NursePassword123!", "name": "Nurse Ayesha", "role": "nurse"},
        {"email": "nurse2@hospital.com", "password": "NursePassword123!", "name": "Nurse Zainab", "role": "nurse"},
    ]
    
    print("\n👥 Creating users...")
    success_count = 0
    
    for user_data in users_to_create:
        if user_data["role"] == "admin":
            if create_admin_user(user_data["email"], user_data["password"], user_data["name"]):
                success_count += 1
        elif user_data["role"] == "doctor":
            if create_doctor_user(user_data["email"], user_data["password"], user_data["name"]):
                success_count += 1
        elif user_data["role"] == "nurse":
            if create_nurse_user(user_data["email"], user_data["password"], user_data["name"]):
                success_count += 1
    
    print(f"\n🎉 Firebase admin setup completed!")
    print(f"✅ Successfully created {success_count}/{len(users_to_create)} users")
    
    print("\n📋 Login Credentials:")
    print("=" * 30)
    for user_data in users_to_create:
        print(f"Email: {user_data['email']}")
        print(f"Password: {user_data['password']}")
        print(f"Role: {user_data['role'].upper()}")
        print(f"Name: {user_data['name']}")
        print("-" * 30)
    
    print("\n🔐 Security Notes:")
    print("- Change passwords after first login")
    print("- Use strong passwords in production")
    print("- Enable 2FA for admin accounts")
    print("- Regular security audits recommended")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
