# Firebase Auth Integration Guide

## Overview
The demo credentials have been removed from the EMR portal. You now need to implement Firebase Authentication to enable secure login for doctors and admins.

## Backend Changes Made

### 1. Updated Login Endpoint (`app/main.py`)
```python
@app.post("/auth/login")
async def login(credentials: dict):
    """Login for doctors and admins using Firebase Auth"""
    try:
        id_token = credentials.get("id_token")
        
        if not id_token:
            return {
                "success": False,
                "error": "Firebase ID token required"
            }
        
        # TODO: Verify Firebase ID token
        # In production, verify the token with Firebase Admin SDK
        
        return {
            "success": False,
            "error": "Firebase Auth integration pending. Please implement Firebase token verification."
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

## Frontend Changes Made

### 1. Removed Demo Credentials
- Removed hardcoded demo users from backend
- Removed demo credential buttons from login screen
- Updated AuthContext to show Firebase Auth required message

### 2. Updated Login Screen
- Removed demo credentials section
- Clean login form ready for Firebase Auth

## Next Steps: Firebase Auth Implementation

### 1. Install Firebase SDK
```bash
cd emr_portal
npm install firebase
```

### 2. Create Firebase Configuration
Create `emr_portal/src/firebase/config.js`:
```javascript
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "your-api-key",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "123456789",
  appId: "your-app-id"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

### 3. Update AuthContext for Firebase
```javascript
import { signInWithEmailAndPassword, signOut } from 'firebase/auth';
import { auth } from '../firebase/config';

const login = async (credentials) => {
  try {
    const { email, password } = credentials;
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const idToken = await userCredential.user.getIdToken();
    
    // Send token to backend for verification
    const response = await axios.post(`${API_BASE_URL}/auth/login`, {
      id_token: idToken
    });
    
    if (response.data.success) {
      setUser(response.data.user);
      setIsAuthenticated(true);
      localStorage.setItem('auth_token', idToken);
      localStorage.setItem('user_data', JSON.stringify(response.data.user));
      toast.success(`Welcome, ${response.data.user.name}!`);
      return { success: true };
    }
  } catch (error) {
    toast.error('Login failed: ' + error.message);
    return { success: false, error: error.message };
  }
};
```

### 4. Update Backend Token Verification
Install Firebase Admin SDK:
```bash
pip install firebase-admin
```

Update `app/main.py`:
```python
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

# Initialize Firebase Admin SDK
cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

@app.post("/auth/login")
async def login(credentials: dict):
    try:
        id_token = credentials.get("id_token")
        
        if not id_token:
            return {"success": False, "error": "Firebase ID token required"}
        
        # Verify Firebase ID token
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        
        # Get user data from Firebase
        user_record = firebase_auth.get_user(uid)
        
        # Map Firebase user to your system
        user_data = {
            "uid": uid,
            "email": user_record.email,
            "name": user_record.display_name or user_record.email,
            "role": "doctor"  # Set based on your logic
        }
        
        return {
            "success": True,
            "user": user_data,
            "message": "Login successful"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 5. Firebase Console Setup
1. Go to Firebase Console
2. Enable Authentication
3. Enable Email/Password authentication
4. Create user accounts for doctors and admins
5. Set up custom claims for roles (optional)

## Security Considerations

1. **Token Verification**: Always verify Firebase ID tokens on the backend
2. **Role Management**: Implement proper role-based access control
3. **Custom Claims**: Use Firebase custom claims for user roles
4. **HTTPS**: Ensure all communication is over HTTPS in production

## Testing

1. Create test users in Firebase Console
2. Test login flow with real Firebase Auth
3. Verify token verification on backend
4. Test role-based access control

## Current Status

✅ **Completed:**
- Removed demo credentials
- Updated backend endpoint structure
- Cleaned up frontend login screen
- Prepared for Firebase Auth integration

🔄 **Next Steps:**
- Implement Firebase Auth SDK
- Set up token verification
- Create user management system
- Test authentication flow

The system is now ready for Firebase Auth integration!

