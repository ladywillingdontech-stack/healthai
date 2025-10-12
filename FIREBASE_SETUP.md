# Firebase Setup Guide for Health AI Bot

## 🔥 **Step 1: Create Firebase Project**

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Create a project"
3. Enter project name: `health-ai-bot` (or your preferred name)
4. Enable Google Analytics (optional)
5. Click "Create project"

## 🔥 **Step 2: Enable Firestore Database**

1. In your Firebase project, go to "Firestore Database"
2. Click "Create database"
3. Choose "Start in test mode" (for development)
4. Select a location (choose closest to your users)
5. Click "Done"

## 🔥 **Step 3: Enable Firebase Storage**

1. Go to "Storage" in Firebase Console
2. Click "Get started"
3. Choose "Start in test mode"
4. Select same location as Firestore
5. Click "Done"

## 🔥 **Step 4: Generate Service Account Key**

1. Go to Project Settings (gear icon)
2. Click "Service accounts" tab
3. Click "Generate new private key"
4. Download the JSON file
5. Rename it to `firebase-service-account.json`
6. Place it in your project root directory

## 🔥 **Step 5: Configure Environment Variables**

Update your `.env` file:

```bash
# Firebase Configuration
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json

# Other Firebase settings (optional - can use service account file instead)
FIREBASE_PRIVATE_KEY_ID=your_private_key_id
FIREBASE_PRIVATE_KEY=your_private_key
FIREBASE_CLIENT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your_client_id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=your_client_cert_url
```

## 🔥 **Step 6: Install Dependencies**

```bash
pip install -r requirements.txt
```

## 🔥 **Step 7: Test Firestore Connection**

```bash
python -c "
from app.firestore_service import firestore_service
print('Firestore connection successful!')
print(f'Project ID: {firestore_service.db.project}')
"
```

## 🔥 **Step 8: Setup Chroma DB**

```bash
python setup_chroma_db.py
```

## 🔥 **Step 9: Start the Backend**

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 🔥 **Firestore Collections Structure**

Your Firestore will have these collections:

```
health_ai_bot/
├── patients/
│   ├── {patient_id}/
│   │   ├── name: string
│   │   ├── phone: string
│   │   ├── age: number
│   │   ├── gender: string
│   │   ├── address: string
│   │   ├── medical_history: array
│   │   ├── created_at: timestamp
│   │   └── updated_at: timestamp
├── doctors/
│   ├── {doctor_id}/
│   │   ├── name: string
│   │   ├── email: string
│   │   ├── specialization: string
│   │   ├── permissions: array
│   │   ├── is_active: boolean
│   │   ├── created_at: timestamp
│   │   └── updated_at: timestamp
├── conversations/
│   ├── {conversation_id}/
│   │   ├── patient_id: string
│   │   ├── messages: array
│   │   ├── status: string
│   │   ├── phase: string
│   │   ├── completed_questions: array
│   │   ├── patient_data: object
│   │   ├── created_at: timestamp
│   │   └── updated_at: timestamp
└── emrs/
    ├── {emr_id}/
    │   ├── patient_id: string
    │   ├── doctor_id: string
    │   ├── data: object
    │   ├── pdf_url: string
    │   ├── status: string
    │   ├── alert_level: string
    │   ├── created_at: timestamp
    │   └── updated_at: timestamp
```

## 🔥 **Security Rules (Optional)**

For production, set up Firestore security rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only authenticated users can access data
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
    
    // Doctors can access patient data
    match /patients/{patientId} {
      allow read, write: if request.auth != null && 
        request.auth.token.role == 'doctor';
    }
    
    // Patients can only access their own data
    match /patients/{patientId} {
      allow read, write: if request.auth != null && 
        request.auth.uid == patientId;
    }
  }
}
```

## 🔥 **Benefits of Using Firestore**

✅ **NoSQL** - Flexible data structure for medical records
✅ **Real-time** - Instant updates for doctors
✅ **Scalable** - Handles any number of patients
✅ **Secure** - Built-in HIPAA compliance
✅ **Integrated** - Works with Firebase Storage
✅ **Cost-effective** - Pay only for what you use
✅ **No maintenance** - Google handles everything
✅ **Offline support** - Flutter app works offline

## 🔥 **Troubleshooting**

### Error: "No module named 'firebase_admin'"
```bash
pip install firebase-admin google-cloud-firestore
```

### Error: "Service account key not found"
- Make sure `firebase-service-account.json` is in project root
- Check file permissions
- Verify JSON format is correct

### Error: "Permission denied"
- Check Firestore security rules
- Verify service account has proper permissions
- Make sure project ID is correct

### Error: "Project not found"
- Verify `FIREBASE_PROJECT_ID` in `.env`
- Check if project exists in Firebase Console
- Ensure service account has access to project

