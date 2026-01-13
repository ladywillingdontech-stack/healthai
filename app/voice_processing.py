import openai
import requests
import tempfile
import os
import asyncio
from typing import Optional
from app.config import settings
import httpx
from app.urdu_converter import urdu_converter


class VoiceProcessor:
    def __init__(self):
        openai.api_key = settings.openai_api_key
        self.elevenlabs_api_key = settings.elevenlabs_api_key
        self.elevenlabs_voice_id = settings.elevenlabs_voice_id
        
        # Rate limiting semaphore for OpenAI Whisper API calls
        self.whisper_semaphore = asyncio.Semaphore(20)  # Max 20 concurrent Whisper calls

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
                # Transcribe using Whisper with better Urdu support (async with rate limiting)
                async with self.whisper_semaphore:
                    loop = asyncio.get_event_loop()
                    
                    def _whisper_call():
                        with open(temp_file_path, "rb") as audio_file:
                            return openai.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language="ur",  # Urdu language code
                                prompt="This is a medical conversation in Urdu. Common words: نام، عمر، جنس، فون، درد، بخار، کھانسی، اُلٹی، خون، تکلیف، ڈاکٹر، ہسپتال، دوائی، علاج"
                            )
                    
                    transcript = await asyncio.wait_for(
                        loop.run_in_executor(None, _whisper_call),
                        timeout=30.0
                    )
                
                return transcript.text
                
            except asyncio.TimeoutError:
                print(f"⚠️ Whisper transcription timed out")
                return "معذرت، میں آپ کی آواز سمجھ نہیں سکا۔"
            except Exception as e:
                print(f"Whisper transcription failed: {e}")
                # Try without language specification as fallback
                try:
                    async with self.whisper_semaphore:
                        loop = asyncio.get_event_loop()
                        
                        def _whisper_fallback():
                            with open(temp_file_path, "rb") as audio_file:
                                return openai.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=audio_file,
                                    prompt="This is a medical conversation in Urdu. Common words: نام، عمر، جنس، فون، درد، بخار، کھانسی، اُلٹی، خون، تکلیف، ڈاکٹر، ہسپتال، دوائی، علاج"
                                )
                        
                        transcript = await asyncio.wait_for(
                            loop.run_in_executor(None, _whisper_fallback),
                            timeout=30.0
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

    async def text_to_speech(self, text: str) -> Optional[str]:
        """Convert text to Urdu speech using ElevenLabs and save to file (async)"""
        try:
            # Convert Roman Urdu to Urdu script for better TTS
            urdu_text = urdu_converter.convert_to_urdu(text, use_ai=True)
            print(f"📝 Original text: {text[:100]}...")
            print(f"📝 Converted to Urdu: {urdu_text[:100]}...")
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            data = {
                "text": urdu_text,  # Use converted Urdu text
                "model_id": "eleven_v3",
                "voice_settings": {
                    "stability": 0.5,           # Voice consistency (0.0-1.0)
                    "similarity_boost": 0.5,     # Voice similarity (0.0-1.0)
                    "style": 0.0,                # Style exaggeration (0.0-1.0)
                    "use_speaker_boost": True    # Enhanced speaker clarity
                }
            }
            
            # Use httpx for async requests
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=headers)
            
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

    async def generate_voice_response(self, text: str) -> Optional[str]:
        """Generate voice response from text (async)"""
        return await self.text_to_speech(text)

    def cleanup_audio_file(self, file_path: str):
        """Clean up temporary audio file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error cleaning up audio file: {e}")


# Initialize voice processor
voice_processor = VoiceProcessor()
