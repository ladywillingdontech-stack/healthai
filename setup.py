#!/usr/bin/env python3
"""
Health AI Bot Setup Script
Sets up the complete healthcare intake system
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = [
        "chroma_db",
        "temp_audio",
        "logs",
        "uploads"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Created directory: {directory}")

def setup_backend():
    """Setup Python backend"""
    print("\n🐍 Setting up Python backend...")
    
    # Install Python dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        return False
    
    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        if os.path.exists("env.example"):
            shutil.copy("env.example", ".env")
            print("📝 Created .env file from template")
        else:
            print("⚠️  Please create .env file with your API keys")
    
    return True

def setup_flutter():
    """Setup Flutter app"""
    print("\n📱 Setting up Flutter app...")
    
    # Check if Flutter is installed
    if not run_command("flutter --version", "Checking Flutter installation"):
        print("❌ Flutter is not installed. Please install Flutter first.")
        return False
    
    # Get Flutter dependencies
    if not run_command("cd flutter_app && flutter pub get", "Getting Flutter dependencies"):
        return False
    
    return True

def setup_react():
    """Setup React app"""
    print("\n⚛️  Setting up React app...")
    
    # Check if Node.js is installed
    if not run_command("node --version", "Checking Node.js installation"):
        print("❌ Node.js is not installed. Please install Node.js first.")
        return False
    
    # Install React dependencies
    if not run_command("cd react_qa_app && npm install", "Installing React dependencies"):
        return False
    
    return True

def create_startup_scripts():
    """Create startup scripts"""
    
    # Backend startup script
    backend_script = """#!/bin/bash
echo "🚀 Starting Health AI Bot Backend..."
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || echo "Virtual environment not found, using system Python"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
    
    with open("start_backend.sh", "w") as f:
        f.write(backend_script)
    os.chmod("start_backend.sh", 0o755)
    
    # Flutter startup script
    flutter_script = """#!/bin/bash
echo "📱 Starting Flutter app..."
cd "$(dirname "$0")/flutter_app"
flutter run
"""
    
    with open("start_flutter.sh", "w") as f:
        f.write(flutter_script)
    os.chmod("start_flutter.sh", 0o755)
    
    # React startup script
    react_script = """#!/bin/bash
echo "⚛️  Starting React QA app..."
cd "$(dirname "$0")/react_qa_app"
npm start
"""
    
    with open("start_react.sh", "w") as f:
        f.write(react_script)
    os.chmod("start_react.sh", 0o755)
    
    print("📜 Created startup scripts")

def main():
    """Main setup function"""
    print("🏥 Health AI Bot - Complete Setup")
    print("=" * 50)
    
    # Create directories
    create_directories()
    
    # Setup backend
    if not setup_backend():
        print("❌ Backend setup failed")
        sys.exit(1)
    
    # Setup Flutter
    if not setup_flutter():
        print("❌ Flutter setup failed")
        sys.exit(1)
    
    # Setup React
    if not setup_react():
        print("❌ React setup failed")
        sys.exit(1)
    
    # Create startup scripts
    create_startup_scripts()
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Update .env file with your API keys")
    print("2. Run: ./start_backend.sh (in one terminal)")
    print("3. Run: ./start_flutter.sh (in another terminal)")
    print("4. Run: ./start_react.sh (in another terminal)")
    print("\n🔗 Access URLs:")
    print("- Backend API: http://localhost:8000")
    print("- Flutter App: Will show in terminal")
    print("- React QA: http://localhost:3000")
    print("\n📚 Documentation: README.md")

if __name__ == "__main__":
    main()
