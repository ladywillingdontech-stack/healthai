# Backend Deployment Guide

## Overview
Your Health AI Bot backend is built with FastAPI and can be deployed on various cloud platforms. Here are the best options with step-by-step instructions.

## 🚀 **Recommended Deployment Options**

### 1. **Railway** (Easiest - Recommended for beginners)
**Pros:** Simple setup, automatic deployments, built-in database
**Cost:** $5/month for hobby plan
**Best for:** Quick deployment, small to medium apps

#### Setup Steps:
1. **Sign up at [Railway.app](https://railway.app)**
2. **Connect your GitHub repository**
3. **Add environment variables:**
   ```
   OPENAI_API_KEY=your_openai_key
   FIREBASE_PROJECT_ID=your_project_id
   FIREBASE_PRIVATE_KEY=your_private_key
   FIREBASE_CLIENT_EMAIL=your_client_email
   ```
4. **Railway will automatically detect Python and install dependencies**
5. **Deploy!** Your app will be live at `https://your-app.railway.app`

---

### 2. **Render** (Great for free tier)
**Pros:** Free tier available, easy setup, automatic SSL
**Cost:** Free tier available, $7/month for paid
**Best for:** Budget-conscious deployments

#### Setup Steps:
1. **Sign up at [Render.com](https://render.com)**
2. **Create new Web Service**
3. **Connect GitHub repository**
4. **Configure build settings:**
   - Build Command: `pip install -r requirements_production.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Add environment variables**
6. **Deploy!**

---

### 3. **Heroku** (Popular choice)
**Pros:** Well-documented, lots of add-ons
**Cost:** $7/month for basic plan
**Best for:** Established platform with good support

#### Setup Steps:
1. **Install Heroku CLI**
2. **Create `Procfile`:**
   ```
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
3. **Deploy:**
   ```bash
   heroku create your-app-name
   heroku config:set OPENAI_API_KEY=your_key
   heroku config:set FIREBASE_PROJECT_ID=your_project_id
   git push heroku main
   ```

---

### 4. **DigitalOcean App Platform** (Good balance)
**Pros:** Competitive pricing, good performance
**Cost:** $5/month for basic plan
**Best for:** Balanced cost and performance

#### Setup Steps:
1. **Sign up at [DigitalOcean](https://digitalocean.com)**
2. **Create new App**
3. **Connect GitHub repository**
4. **Configure app settings**
5. **Add environment variables**
6. **Deploy!**

---

### 5. **AWS EC2** (Most control)
**Pros:** Full control, scalable, enterprise-grade
**Cost:** $3.50/month for t2.micro (free tier eligible)
**Best for:** Advanced users, high traffic

#### Setup Steps:
1. **Launch EC2 instance (Ubuntu)**
2. **SSH into instance:**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```
3. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip nginx
   ```
4. **Clone and setup your app:**
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   pip3 install -r requirements_production.txt
   ```
5. **Setup systemd service**
6. **Configure Nginx reverse proxy**

---

## 🔧 **Pre-Deployment Checklist**

### 1. **Update Requirements File**
Make sure `requirements_production.txt` includes all dependencies:
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
openai==1.3.0
firebase-admin==6.2.0
python-dotenv==1.0.0
```

### 2. **Environment Variables**
Create a `.env` file for local testing:
```env
OPENAI_API_KEY=your_openai_api_key
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYour private key\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your_service_account_email
```

### 3. **Update CORS Settings**
In `app/main.py`, update CORS origins:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # Update this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. **Test Locally**
```bash
# Test production setup
pip install -r requirements_production.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 📱 **Frontend Deployment**

### **Netlify** (Recommended for React)
1. **Build your React app:**
   ```bash
   cd emr_portal
   npm run build
   ```
2. **Deploy to Netlify:**
   - Connect GitHub repository
   - Build command: `npm run build`
   - Publish directory: `build`
   - Add environment variable: `REACT_APP_API_URL=https://your-backend-url.com`

### **Vercel** (Alternative)
1. **Install Vercel CLI:**
   ```bash
   npm i -g vercel
   ```
2. **Deploy:**
   ```bash
   cd emr_portal
   vercel
   ```

---

## 🔒 **Security Considerations**

### 1. **Environment Variables**
- Never commit API keys to Git
- Use platform-specific secret management
- Rotate keys regularly

### 2. **HTTPS**
- Most platforms provide automatic SSL
- Ensure all API calls use HTTPS

### 3. **CORS Configuration**
- Only allow your frontend domain
- Remove wildcard origins in production

### 4. **Rate Limiting**
Consider adding rate limiting:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/process-patient-response")
@limiter.limit("10/minute")
async def process_patient_response(request: Request, ...):
    # Your code here
```

---

## 📊 **Monitoring & Logging**

### 1. **Add Logging**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/process-patient-response")
async def process_patient_response(...):
    logger.info(f"Processing response for patient {patient_id}")
    # Your code here
```

### 2. **Health Check Endpoint**
```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
```

---

## 🎯 **Quick Start Recommendation**

**For beginners:** Use **Railway** or **Render**
1. Push your code to GitHub
2. Connect to Railway/Render
3. Add environment variables
4. Deploy!

**For production:** Use **AWS EC2** or **DigitalOcean**
1. More control and customization
2. Better for scaling
3. More cost-effective for high traffic

---

## 📞 **Support**

If you encounter issues:
1. Check platform-specific documentation
2. Verify environment variables are set correctly
3. Check logs for error messages
4. Ensure all dependencies are in requirements file

**Next Steps:**
1. Choose your deployment platform
2. Set up your GitHub repository
3. Configure environment variables
4. Deploy and test!

Would you like me to help you with any specific platform setup?

