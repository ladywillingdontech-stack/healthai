import openai
import requests
import tempfile
import os
from typing import Optional
from app.config import settings
import httpx
from app.urdu_converter import urdu_converter


class VoiceProcessor:
    def __init__(self):
        openai.api_key = settings.openai_api_key
        self.elevenlabs_api_key = settings.elevenlabs_api_key
        self.elevenlabs_voice_id = settings.elevenlabs_voice_id

    async def speech_to_text(self, audio_path: str) -> str:
        """Convert audio to text using OpenAI Whisper"""
        try:
            # Check if it's a URL or file path
            if audio_path.startswith(('http://', 'https://')):
                # Download audio file
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_path)
                    audio_data = response.content
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_file_path = temp_file.name
            else:
                # It's already a file path
                temp_file_path = audio_path
            
            try:
                # Transcribe using Whisper with better Urdu support
                with open(temp_file_path, "rb") as audio_file:
                    transcript = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ur",  # Urdu language code
                        prompt="This is a medical conversation in Urdu. Common words: نام، عمر، جنس، فون، درد، بخار، کھانسی، اُلٹی، خون، تکلیف، ڈاکٹر، ہسپتال، دوائی، علاج"
                    )
                
                return transcript.text
                
            except Exception as e:
                print(f"Whisper transcription failed: {e}")
                # Try without language specification as fallback
                try:
                    with open(temp_file_path, "rb") as audio_file:
                        transcript = openai.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            prompt="This is a medical conversation in Urdu. Common words: نام، عمر، جنس، فون، درد، بخار، کھانسی، اُلٹی، خون، تکلیف، ڈاکٹر، ہسپتال، دوائی، علاج"
                        )
                    return transcript.text
                except Exception as e2:
                    print(f"Fallback transcription also failed: {e2}")
                    return "معذرت، میں آپ کی آواز سمجھ نہیں سکا۔"
                
            finally:
                # Clean up temporary file only if we created it
                if audio_path.startswith(('http://', 'https://')) and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                
        except Exception as e:
            print(f"Error in speech-to-text: {e}")
            return ""

    def text_to_speech(self, text: str, prefer_openai: bool = True) -> Optional[str]:
        """
        Convert text to Urdu speech
        
        Args:
            text: Text to convert to speech
            prefer_openai: If True, try OpenAI TTS first (better Urdu pronunciation), 
                          otherwise use ElevenLabs first
        """
        try:
            # Convert Roman Urdu to Urdu script for better TTS
            urdu_text = urdu_converter.convert_to_urdu(text, use_ai=True)
            print(f"📝 Original text: {text[:100]}...")
            print(f"📝 Converted to Urdu: {urdu_text[:100]}...")
            
            # Normalize Urdu text for better pronunciation
            urdu_text = self._normalize_urdu_text(urdu_text)
            
            # Try OpenAI TTS first if preferred (better Urdu support)
            if prefer_openai:
                openai_result = self._text_to_speech_openai_fallback(text)
                if openai_result:
                    return openai_result
                print("⚠️ OpenAI TTS not available, falling back to ElevenLabs")
            
            # Use ElevenLabs with optimized settings
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            # Optimized settings for Urdu pronunciation
            # Note: These settings are tuned for better multilingual/Urdu support
            data = {
                "text": urdu_text,  # Use converted and normalized Urdu text
                "model_id": "eleven_multilingual_v2",  # Best model for multilingual support
                "voice_settings": {
                    "stability": 0.75,          # Higher stability for consistent pronunciation
                    "similarity_boost": 0.75,    # Higher similarity for better voice matching
                    "style": 0.0,                # No style exaggeration for clear speech
                    "use_speaker_boost": True     # Enhanced speaker clarity
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                # Save audio to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
                
                print(f"✅ Audio saved to: {temp_file_path}")
                return temp_file_path
            else:
                print(f"❌ ElevenLabs API error: {response.status_code} - {response.text}")
                # Try OpenAI fallback if ElevenLabs fails and we haven't tried it yet
                if not prefer_openai:
                    print("🔄 Trying OpenAI TTS as fallback...")
                    return self._text_to_speech_openai_fallback(text)
                return None
                
        except Exception as e:
            print(f"❌ Error in text-to-speech: {e}")
            # Try fallback on error
            if prefer_openai:
                print("🔄 Trying ElevenLabs as fallback...")
                # Try ElevenLabs directly without OpenAI
                return self._text_to_speech_elevenlabs_only(text)
            else:
                print("🔄 Trying OpenAI TTS as fallback...")
                return self._text_to_speech_openai_fallback(text)
    
    def _text_to_speech_elevenlabs_only(self, text: str) -> Optional[str]:
        """Use only ElevenLabs TTS (internal method)"""
        try:
            urdu_text = urdu_converter.convert_to_urdu(text, use_ai=True)
            urdu_text = self._normalize_urdu_text(urdu_text)
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            data = {
                "text": urdu_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.75,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    temp_file.write(response.content)
                    return temp_file.name
            return None
        except Exception as e:
            print(f"❌ ElevenLabs TTS error: {e}")
            return None
    
    def _normalize_urdu_text(self, text: str) -> str:
        """Normalize Urdu text for better TTS pronunciation"""
        import re
        
        # Ensure proper spacing around punctuation
        text = re.sub(r'([؟،۔])([^\s])', r'\1 \2', text)  # Space after punctuation
        text = re.sub(r'([^\s])([؟،۔])', r'\1 \2', text)  # Space before punctuation
        
        # Fix common spacing issues
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
        text = text.strip()
        
        # Add pauses for better pronunciation (add space after common conjunctions)
        # This helps TTS engines better identify sentence boundaries
        pause_markers = ['؟', '،', '۔', '.', '!', '?']
        for marker in pause_markers:
            text = text.replace(marker, marker + ' ')
        
        # Normalize again after adding pauses
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _text_to_speech_openai_fallback(self, text: str) -> Optional[str]:
        """Fallback to OpenAI TTS if available (better Urdu support)"""
        try:
            # OpenAI TTS might have better Urdu pronunciation
            urdu_text = urdu_converter.convert_to_urdu(text, use_ai=True)
            urdu_text = self._normalize_urdu_text(urdu_text)
            
            response = openai.audio.speech.create(
                model="tts-1-hd",  # High quality model
                voice="nova",  # Natural sounding voice
                input=urdu_text,
                speed=1.0
            )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                for chunk in response.iter_bytes():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            print(f"✅ Audio saved using OpenAI TTS: {temp_file_path}")
            return temp_file_path
            
        except Exception as e:
            print(f"⚠️ OpenAI TTS fallback failed: {e}")
            return None

    async def process_voice_message(self, audio_url: str) -> str:
        """Complete voice processing pipeline: STT -> process -> TTS"""
        # Convert speech to text
        text = await self.speech_to_text(audio_url)
        return text

    def generate_voice_response(self, text: str) -> Optional[str]:
        """Generate voice response from text"""
        return self.text_to_speech(text)

    def cleanup_audio_file(self, file_path: str):
        """Clean up temporary audio file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error cleaning up audio file: {e}")


# Initialize voice processor
voice_processor = VoiceProcessor()
