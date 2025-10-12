# Meta WhatsApp Business API Setup Guide

## 📱 **Step 1: Create Meta Developer Account**

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click "Get Started" or "My Apps"
3. Click "Create App"
4. Choose "Business" as app type
5. Enter app name: "Health AI Bot"
6. Enter contact email
7. Click "Create App"

## 📱 **Step 2: Add WhatsApp Product**

1. In your app dashboard, find "WhatsApp" product
2. Click "Set up" on WhatsApp
3. Choose "Business" account type
4. Follow the setup wizard

## 📱 **Step 3: Get Phone Number**

### **Option A: Use Existing Number**
1. If you have a WhatsApp Business number, verify it
2. Go to WhatsApp > Getting Started
3. Click "Add phone number"
4. Enter your phone number
5. Verify with SMS code

### **Option B: Get New Number**
1. Go to WhatsApp > Getting Started
2. Click "Add phone number"
3. Choose "I don't have a phone number"
4. Follow instructions to get a new number

## 📱 **Step 4: Get API Credentials**

### **Access Token:**
1. Go to WhatsApp > Getting Started
2. Find "Temporary access token"
3. Copy the token (starts with `EAA...`)
4. **Note:** This is temporary, you'll need permanent token later

### **Phone Number ID:**
1. In WhatsApp > Getting Started
2. Find "Phone number ID"
3. Copy the ID (numeric value)

### **Verify Token:**
1. Go to WhatsApp > Configuration
2. Set a verify token (any string you want)
3. Remember this token for webhook setup

## 📱 **Step 5: Configure Webhook**

### **Webhook URL:**
```
https://your-domain.com/whatsapp/webhook
```

### **For Development (using ngrok):**
```bash
# Install ngrok
npm install -g ngrok

# Start your backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, expose your local server
ngrok http 8000

# Use the ngrok URL as webhook URL
# Example: https://abc123.ngrok.io/whatsapp/webhook
```

### **Webhook Configuration:**
1. Go to WhatsApp > Configuration
2. Click "Edit" on Webhook
3. Enter your webhook URL
4. Enter verify token (same as step 4)
5. Subscribe to `messages` field
6. Click "Verify and Save"

## 📱 **Step 6: Update Environment Variables**

Create `.env` file:
```bash
# Meta WhatsApp Business API Configuration
WHATSAPP_ACCESS_TOKEN=EAA_your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=your_verify_token_here
WHATSAPP_API_VERSION=v18.0

# Other configurations...
OPENAI_API_KEY=sk-your_openai_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
FIREBASE_PROJECT_ID=your_firebase_project_id
```

## 📱 **Step 7: Test WhatsApp Integration**

### **Test Webhook:**
```bash
# Start your backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test webhook verification
curl "http://localhost:8000/whatsapp/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=your_verify_token"
```

### **Test Sending Message:**
```python
from app.whatsapp_meta_service import whatsapp_service

# Send text message
whatsapp_service.send_text_message("+1234567890", "Hello from Health AI Bot!")

# Send voice message
whatsapp_service.send_voice_message("+1234567890", "https://example.com/audio.mp3")
```

## 📱 **Step 8: Get Permanent Access Token**

### **For Production:**
1. Go to WhatsApp > Getting Started
2. Click "Generate Token" under "Permanent access token"
3. Choose your app
4. Copy the permanent token
5. Update your `.env` file

### **For Development:**
- Temporary token works for 24 hours
- Regenerate when needed

## 📱 **Step 9: Message Templates (Optional)**

### **Create Message Templates:**
1. Go to WhatsApp > Message Templates
2. Click "Create Template"
3. Choose template type (e.g., "Text")
4. Enter template name and content
5. Submit for approval

### **Use Templates:**
```python
# Send template message
whatsapp_service.send_template_message(
    to_number="+1234567890",
    template_name="hello_world",
    language_code="en"
)
```

## 📱 **Step 10: Production Deployment**

### **Webhook URL:**
```
https://your-production-domain.com/whatsapp/webhook
```

### **SSL Certificate:**
- Required for production webhook
- Use Let's Encrypt or your SSL provider

### **Environment Variables:**
- Set all required environment variables
- Use permanent access token
- Configure proper logging

## 📱 **API Rate Limits**

### **Message Limits:**
- **Tier 1:** 1,000 messages per day
- **Tier 2:** 10,000 messages per day
- **Tier 3:** 100,000 messages per day

### **Rate Limits:**
- **Text messages:** 80 per second
- **Media messages:** 16 per second
- **Template messages:** 250 per second

## 📱 **Cost Structure**

### **Conversation-based Pricing:**
- **Free tier:** 1,000 conversations per month
- **Paid tier:** $0.005 per conversation after free tier

### **Conversation Types:**
- **User-initiated:** User sends message first
- **Business-initiated:** Business sends message first (requires template)

## 📱 **Troubleshooting**

### **Common Issues:**

#### **Webhook Verification Failed:**
- Check verify token matches
- Ensure webhook URL is accessible
- Check SSL certificate

#### **Message Not Sent:**
- Verify access token is valid
- Check phone number ID
- Ensure recipient has WhatsApp

#### **Media Upload Failed:**
- Check file size (max 16MB)
- Verify file format (MP3, MP4, etc.)
- Check network connection

### **Debug Mode:**
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📱 **Security Best Practices**

1. **Keep access token secure**
2. **Use environment variables**
3. **Rotate tokens regularly**
4. **Monitor API usage**
5. **Implement rate limiting**
6. **Log all webhook events**

## 📱 **Testing Checklist**

- [ ] Webhook verification works
- [ ] Can receive messages
- [ ] Can send text messages
- [ ] Can send voice messages
- [ ] Can upload media
- [ ] Error handling works
- [ ] Rate limiting implemented
- [ ] Logging configured

## 📱 **Production Checklist**

- [ ] Permanent access token
- [ ] SSL certificate
- [ ] Domain configured
- [ ] Monitoring setup
- [ ] Error alerts
- [ ] Backup webhook
- [ ] Rate limiting
- [ ] Security audit

## 📱 **Support Resources**

- [Meta WhatsApp Business API Docs](https://developers.facebook.com/docs/whatsapp)
- [Webhook Reference](https://developers.facebook.com/docs/whatsapp/webhooks)
- [Message Templates](https://developers.facebook.com/docs/whatsapp/message-templates)
- [Rate Limits](https://developers.facebook.com/docs/whatsapp/rate-limits)









