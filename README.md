# 🏥 Health AI Bot - Healthcare Intake System

A comprehensive AI-powered healthcare intake system that enables patients to interact with an AI bot via WhatsApp voice messages in Urdu, with automated EMR generation and doctor/admin management interfaces.

## 🌟 Features

### Patient Experience
- **Voice-only interaction** via WhatsApp in Urdu
- **AI-powered conversation** with dynamic follow-up questions
- **Structured intake process**: Onboarding → Demographics → Symptoms → Summary
- **Alert detection** for red (emergency) and yellow (urgent) cases
- **Automatic EMR generation** in both JSON and PDF formats

### Doctor/Admin Features
- **Flutter mobile app** for EMR management
- **Real-time dashboard** with alert monitoring
- **PDF viewing and download** capabilities
- **Patient data management** and analytics
- **Role-based access** (Doctor/Admin)

### Developer Tools
- **React QA interface** for testing voice processing
- **Conversation flow testing** with different phases
- **EMR viewer** with JSON inspection
- **Chroma DB setup** for question management

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   FastAPI       │    │   Chroma DB     │
│   Voice Input   │───▶│   Backend       │───▶│   Questions     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   GPT-4 +       │    │   Firebase      │
                       │   ElevenLabs    │    │   Storage       │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Flutter App   │    │   React QA      │
                       │   (Doctors)     │    │   (Testing)     │
                       └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- Flutter SDK
- PostgreSQL (or use SQLite for development)
- API Keys:
  - OpenAI API Key
  - ElevenLabs API Key
  - Twilio Account (WhatsApp)
  - Firebase Project

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd health-ai-bot
   ```

2. **Run the setup script**
   ```bash
   python setup.py
   ```

3. **Configure environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

4. **Start the services**
   ```bash
   # Terminal 1: Backend
   ./start_backend.sh
   
   # Terminal 2: Flutter App
   ./start_flutter.sh
   
   # Terminal 3: React QA
   ./start_react.sh
   ```

## 🔧 Configuration

### Environment Variables (.env)

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
OPENAI_CHAT_MODEL=gpt-4

# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=your_urdu_voice_id_here

# Twilio WhatsApp Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Firebase Configuration
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_PRIVATE_KEY_ID=your_private_key_id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nyour_private_key_here\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your_client_email
FIREBASE_CLIENT_ID=your_client_id
FIREBASE_CLIENT_X509_CERT_URL=your_client_cert_url

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/health_ai_bot
CHROMA_DB_PATH=./chroma_db

# Security
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 📱 Usage

### 1. Setup Chroma DB

Upload your questions PDF to initialize the knowledge base:

```bash
# Via API
curl -X POST "http://localhost:8000/setup/chroma" \
  -F "pdf=@questions.pdf"

# Via React QA interface
# Go to http://localhost:3000 → Setup tab → Upload PDF
```

### 2. Test Voice Processing

Use the React QA interface to test voice processing:

1. Go to http://localhost:3000
2. Click "Voice Testing" tab
3. Record audio in Urdu
4. Test speech-to-text and text-to-speech

### 3. Test Conversation Flow

Test the conversation engine:

1. Go to "Conversation Testing" tab
2. Select conversation phase
3. Enter patient response
4. View AI-generated follow-up

### 4. Monitor EMRs

View generated EMRs:

1. Go to "EMR Viewer" tab
2. Filter by alert status
3. View detailed EMR information
4. Download PDFs

### 5. Doctor Portal

Access the Flutter app:

1. Run Flutter app
2. Login with demo credentials:
   - Admin: admin@healthai.com / admin123
   - Doctor: doctor@healthai.com / doctor123
3. View dashboard and manage EMRs

## 🔄 WhatsApp Integration

### Webhook Setup

1. **Configure Twilio webhook**:
   - URL: `https://your-domain.com/whatsapp/webhook`
   - Method: POST

2. **Test webhook**:
   ```bash
   curl -X POST "http://localhost:8000/whatsapp/webhook" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "From=whatsapp:+1234567890&MessageType=audio&MediaUrl0=https://example.com/audio.ogg"
   ```

### Voice Message Flow

1. Patient sends voice message via WhatsApp
2. Twilio webhook receives the message
3. Backend downloads audio and converts to text (Whisper)
4. Conversation engine processes the text
5. AI generates response and converts to speech (ElevenLabs)
6. Voice response sent back via WhatsApp

## 🏥 EMR Generation

### JSON Format

```json
{
  "patient_id": "uuid",
  "session_id": "session_123",
  "demographics": {
    "age": 35,
    "gender": "female",
    "children": 2
  },
  "onboarding": {
    "marital_status": "married",
    "family_history": "diabetes"
  },
  "symptoms": [
    {
      "symptom": "chest pain",
      "duration": "2 days",
      "details": "sharp pain radiating to arm"
    }
  ],
  "alerts": {
    "status": "red",
    "reason": "chest pain with shortness of breath"
  },
  "ai_summary": "Patient reports acute chest pain...",
  "pdf_url": "https://firebase.storage/emrs/emr_123.pdf"
}
```

### PDF Generation

- Professional medical record format
- Patient information and demographics
- Symptom details and timeline
- Alert status and recommendations
- AI-generated clinical summary
- Stored in Firebase Storage

## 🚨 Alert System

### Red Alerts (Emergency)
- Chest pain + breathlessness
- Fainting or loss of consciousness
- Severe bleeding
- Heart attack symptoms

**Response**: "🚨 آپ کی علامات خطرناک ہو سکتی ہیں، براہ کرم فوراً اپنے ڈاکٹر سے رابطہ کریں۔"

### Yellow Alerts (Urgent)
- Mild cough or headache
- Fatigue or general discomfort
- Non-emergency symptoms

**Response**: "⚠️ آپ کو ڈاکٹر سے مشورہ کرنا چاہیے جب آپ کے پاس وقت ہو۔ یہ ایمرجنسی نہیں ہے۔"

## 🔒 Security & Compliance

### HIPAA Compliance
- End-to-end encryption for voice messages
- Secure data transmission
- Access logging and audit trails
- Role-based access control

### Data Protection
- Patient data anonymization
- Secure API authentication
- Regular security updates
- GDPR compliance features

## 🧪 Testing

### Unit Tests
```bash
# Backend tests
cd app
python -m pytest tests/

# Flutter tests
cd flutter_app
flutter test

# React tests
cd react_qa_app
npm test
```

### Integration Tests
```bash
# Test complete voice pipeline
curl -X POST "http://localhost:8000/test/voice" \
  -F "audio=@test_audio.webm"

# Test conversation flow
curl -X POST "http://localhost:8000/test/conversation" \
  -H "Content-Type: application/json" \
  -d '{"patient_text": "میرے سینے میں درد ہے", "current_phase": "symptom"}'
```

## 📊 Monitoring & Analytics

### Dashboard Metrics
- Total EMRs generated
- Red/Yellow alert counts
- Patient demographics
- Conversation completion rates

### Logging
- Voice processing logs
- Conversation flow tracking
- Error monitoring
- Performance metrics

## 🚀 Deployment

### Production Setup

1. **Environment Configuration**
   ```bash
   # Set production environment variables
   export DEBUG=False
   export DATABASE_URL=postgresql://prod_user:password@prod_host:5432/health_ai_bot
   ```

2. **Database Migration**
   ```bash
   alembic upgrade head
   ```

3. **Static Files**
   ```bash
   # Build React app
   cd react_qa_app && npm run build
   
   # Build Flutter app
   cd flutter_app && flutter build apk
   ```

4. **Docker Deployment**
   ```bash
   docker-compose up -d
   ```

### Scaling Considerations

- **Load Balancing**: Use nginx or similar
- **Database**: PostgreSQL with read replicas
- **Caching**: Redis for session management
- **CDN**: For static assets and PDFs
- **Monitoring**: Prometheus + Grafana

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: [Wiki](link-to-wiki)
- **Issues**: [GitHub Issues](link-to-issues)
- **Discussions**: [GitHub Discussions](link-to-discussions)
- **Email**: support@healthaibot.com

## 🙏 Acknowledgments

- OpenAI for GPT-4 and Whisper
- ElevenLabs for TTS
- Twilio for WhatsApp integration
- Firebase for storage
- The open-source community

---

**⚠️ Important**: This system is for healthcare use and must comply with local medical regulations and privacy laws. Ensure proper testing and validation before production deployment.
