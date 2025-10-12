# 🚀 Railway Deployment Guide for Health AI Bot

## **Step-by-Step Railway Deployment**

### **Step 1: Prepare Your Code**

✅ **Files Created:**
- `Procfile` - Tells Railway how to run your app
- `railway.json` - Railway configuration
- Updated `app/main.py` with health check endpoint

### **Step 2: Push to GitHub**

1. **Initialize Git repository** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Railway deployment"
   ```

2. **Create GitHub repository:**
   - Go to [GitHub.com](https://github.com)
   - Click "New repository"
   - Name it: `health-ai-bot`
   - Make it public or private (your choice)

3. **Push to GitHub:**
   ```bash
   git remote add origin https://github.com/your-username/health-ai-bot.git
   git branch -M main
   git push -u origin main
   ```

### **Step 3: Deploy to Railway**

1. **Sign up for Railway:**
   - Go to [Railway.app](https://railway.app)
   - Click "Sign up" and connect with GitHub

2. **Create New Project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `health-ai-bot` repository

3. **Configure Environment Variables:**
   - Go to your project dashboard
   - Click on "Variables" tab
   - Add these environment variables:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   FIREBASE_PROJECT_ID=your_firebase_project_id
   FIREBASE_PRIVATE_KEY=your_firebase_private_key
   FIREBASE_CLIENT_EMAIL=your_firebase_client_email
   ```

4. **Deploy:**
   - Railway will automatically detect Python
   - It will install dependencies from `requirements_production.txt`
   - Your app will be deployed!

### **Step 4: Get Your Railway URL**

After deployment, Railway will give you a URL like:
```
https://health-ai-bot-production-xxxx.up.railway.app
```

**Test your deployment:**
- Visit: `https://your-url.railway.app/health`
- You should see: `{"status": "healthy", "timestamp": "...", "service": "Health AI Bot API"}`

### **Step 5: Update Frontend Configuration**

1. **Update EMR Portal API URL:**
   - In `emr_portal/src/contexts/AuthContext.js`
   - Change `API_BASE_URL` to your Railway URL:
   ```javascript
   const API_BASE_URL = 'https://your-app-name-production-xxxx.up.railway.app';
   ```

2. **Deploy Frontend to Netlify:**
   - Go to [Netlify.com](https://netlify.com)
   - Connect your GitHub repository
   - Build command: `npm run build`
   - Publish directory: `build`
   - Add environment variable: `REACT_APP_API_URL=https://your-railway-url.railway.app`

### **Step 6: Update CORS Settings**

After getting your frontend URL, update CORS in your Railway app:

1. **Go to Railway dashboard**
2. **Click on your service**
3. **Go to Variables tab**
4. **Add new variable:**
   ```
   FRONTEND_URL=https://your-netlify-app.netlify.app
   ```

5. **Update your code** to use this variable:
   ```python
   # In app/main.py
   import os
   
   frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
   
   app.add_middleware(
       CORSMiddleware,
       allow_origins=[
           "http://localhost:3000",
           frontend_url,
       ],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

### **Step 7: Test Everything**

1. **Backend Health Check:**
   - Visit: `https://your-railway-url.railway.app/health`

2. **API Endpoints:**
   - Test: `https://your-railway-url.railway.app/docs` (FastAPI docs)

3. **Frontend:**
   - Visit your Netlify URL
   - Try logging in with demo credentials
   - Test EMR functionality

## **Railway Pricing**

- **Hobby Plan:** $5/month
  - 512MB RAM
  - $5 credit included
  - Perfect for your app

- **Pro Plan:** $20/month
  - 8GB RAM
  - $20 credit included
  - For high-traffic apps

## **Railway Features You'll Love**

✅ **Automatic Deployments:** Push to GitHub = automatic deployment
✅ **Built-in SSL:** HTTPS enabled by default
✅ **Environment Variables:** Easy secret management
✅ **Logs:** Real-time application logs
✅ **Metrics:** CPU, memory, and network monitoring
✅ **Custom Domains:** Add your own domain name

## **Troubleshooting**

### **Common Issues:**

1. **Build Fails:**
   - Check `requirements_production.txt` has all dependencies
   - Check Railway logs for specific errors

2. **Environment Variables Not Working:**
   - Make sure variable names match exactly
   - Check for typos in variable names

3. **CORS Errors:**
   - Update CORS origins with your frontend URL
   - Make sure frontend URL is correct

4. **App Crashes:**
   - Check Railway logs
   - Verify all environment variables are set
   - Test locally first

### **Railway Logs:**
- Go to your Railway dashboard
- Click on your service
- Click "Logs" tab
- See real-time logs

## **Next Steps After Deployment**

1. **Set up custom domain** (optional)
2. **Configure monitoring** and alerts
3. **Set up database backups** (if using Railway database)
4. **Configure CI/CD** for automatic deployments

## **Success! 🎉**

Your Health AI Bot backend is now live on Railway! 

**Your API will be available at:**
```
https://your-app-name-production-xxxx.up.railway.app
```

**Test endpoints:**
- Health: `/health`
- API Docs: `/docs`
- All your existing endpoints work the same!

Would you like me to help you with any specific part of the deployment process?
