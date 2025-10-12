#!/usr/bin/env python3
"""
Setup Chroma DB with Questions.pdf
This script processes the Questions.pdf file and stores the questions in Chroma DB
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.urdu_transliteration_parser import UrduChromaDBSetup
from app.config import settings

def main():
    """Main function to setup Chroma DB with Questions.pdf"""
    print("🏥 Health AI Bot - Chroma DB Setup")
    print("=" * 50)
    
    # Check if Questions.pdf exists
    pdf_path = "Questions.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ Error: {pdf_path} not found in current directory")
        print("Please make sure Questions.pdf is in the project root directory")
        return False
    
    print(f"📄 Found Questions.pdf: {os.path.getsize(pdf_path)} bytes")
    
    try:
        # Setup Chroma DB with Urdu transliteration parsing
        print("🔄 Processing PDF with Urdu transliteration parser...")
        urdu_setup = UrduChromaDBSetup()
        question_count = urdu_setup.setup_with_urdu_parsing(pdf_path)
        
        print(f"✅ Successfully processed {question_count} questions from Questions.pdf")
        print("📚 Questions are now stored in Chroma DB and ready for retrieval")
        
        # Test retrieval
        print("\n🧪 Testing question retrieval...")
        
        # Test onboarding questions
        onboarding_questions = chroma_setup.get_questions_by_type("onboarding")
        print(f"📋 Found {len(onboarding_questions)} onboarding questions")
        
        # Test demographic questions
        demographic_questions = chroma_setup.get_questions_by_type("demographic")
        print(f"👥 Found {len(demographic_questions)} demographic questions")
        
        # Test symptom questions
        symptom_questions = chroma_setup.get_questions_by_type("symptom")
        print(f"🩺 Found {len(symptom_questions)} symptom questions")
        
        # Show sample questions
        if onboarding_questions:
            print(f"\n📝 Sample onboarding question:")
            print(f"   {onboarding_questions[0]['question_text']}")
        
        if demographic_questions:
            print(f"\n📝 Sample demographic question:")
            print(f"   {demographic_questions[0]['question_text']}")
        
        if symptom_questions:
            print(f"\n📝 Sample symptom question:")
            print(f"   {symptom_questions[0]['question_text']}")
        
        print("\n🎉 Chroma DB setup completed successfully!")
        print("The system is now ready to use the questions for patient intake conversations.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up Chroma DB: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have installed all dependencies: pip install -r requirements.txt")
        print("2. Check that your .env file has the correct OpenAI API key")
        print("3. Ensure the PDF file is not corrupted")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
