import openai
import requests
import tempfile
import os
from typing import Optional
from app.config import settings
import httpx


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

    def text_to_speech(self, text: str) -> Optional[str]:
        """Convert text to Urdu speech using ElevenLabs and save to file"""
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,           # Voice consistency (0.0-1.0)
                    "similarity_boost": 0.5,     # Voice similarity (0.0-1.0)
                    "style": 0.0,                # Style exaggeration (0.0-1.0)
                    "use_speaker_boost": True    # Enhanced speaker clarity
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
                print(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error in text-to-speech: {e}")
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
