"""
Meta WhatsApp Business API Integration
Handles sending and receiving WhatsApp messages using Meta's official API
"""

import httpx
import json
import os
import asyncio
import time
from typing import Optional, Dict, Any
from app.config import settings

class MetaWhatsAppService:
    def __init__(self):
        self.access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.verify_token = settings.whatsapp_verify_token
        # Let WhatsApp decide the API version automatically
        self.base_url = f"https://graph.facebook.com/{self.phone_number_id}"
        
        # Create async HTTP client with connection pooling for better performance
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),  # 30s total, 10s connect
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            http2=True  # Use HTTP/2 for better performance
        )
        
        # Rate limiting semaphore to prevent overwhelming WhatsApp API
        self.api_semaphore = asyncio.Semaphore(20)  # Max 20 concurrent API calls
        
        # Message deduplication: Track processed message IDs with timestamps
        # Format: {message_id: timestamp}
        self.processed_messages: Dict[str, float] = {}
        
        # Per-patient locks to prevent concurrent processing
        # Format: {patient_id: asyncio.Lock}
        self.patient_locks: Dict[str, asyncio.Lock] = {}
        
        # Lock for managing patient_locks dictionary (using threading.Lock for sync access)
        import threading
        self.locks_lock = threading.Lock()
        
        # Track last response sent per patient to prevent duplicate responses
        # Format: {patient_id: (message_id, timestamp)}
        self.last_response: Dict[str, tuple] = {}
        
        # Cleanup old processed messages every 5 minutes (keep for 1 hour)
        self.message_ttl = 3600  # 1 hour in seconds
    
    async def close_http_client(self):
        """Close HTTP client on shutdown"""
        await self.http_client.aclose()
        
    
    async def send_voice_message(self, to_number: str, audio_url: str) -> bool:
        """Send a voice message via WhatsApp (async)"""
        async with self.api_semaphore:
            try:
                url = f"{self.base_url}/messages"
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": "audio",
                    "audio": {
                        "link": audio_url
                    }
                }
                
                response = await self.http_client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                print(f"✅ Voice message sent to {to_number}")
                return True
                
            except httpx.HTTPError as e:
                print(f"❌ Error sending voice message: {e}")
                return False
    
    async def send_media_message(self, to_number: str, media_url: str, media_type: str = "audio") -> bool:
        """Send media message (audio, image, document) via WhatsApp (async)"""
        async with self.api_semaphore:
            try:
                url = f"{self.base_url}/messages"
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": media_type,
                    media_type: {
                        "link": media_url
                    }
                }
                
                response = await self.http_client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                print(f"✅ {media_type} message sent to {to_number}")
                return True
                
            except httpx.HTTPError as e:
                print(f"❌ Error sending {media_type} message: {e}")
                return False
    
    def send_template_message(self, to_number: str, template_name: str, language_code: str = "en", components: list = None) -> bool:
        """Send a template message via WhatsApp"""
        try:
            url = f"{self.base_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    }
                }
            }
            
            if components:
                data["template"]["components"] = components
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print(f"✅ Template message sent to {to_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending template message: {e}")
            return False
    
    async def upload_media(self, media_file_path: str, media_type: str = "audio") -> Optional[str]:
        """Upload media file to WhatsApp servers and get media ID (async)"""
        async with self.api_semaphore:
            try:
                url = f"https://graph.facebook.com/{self.phone_number_id}/media"
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }
                
                # Determine correct MIME type based on file extension
                file_extension = os.path.splitext(media_file_path)[1].lower()
                mime_type_map = {
                    '.mp3': 'audio/mpeg',
                    '.wav': 'audio/wav', 
                    '.ogg': 'audio/ogg',
                    '.aac': 'audio/aac',
                    '.mp4': 'audio/mp4',
                    '.amr': 'audio/amr',
                    '.opus': 'audio/opus'
                }
                mime_type = mime_type_map.get(file_extension, 'audio/mpeg')
                
                # Read file content
                with open(media_file_path, 'rb') as file:
                    file_content = file.read()
                
                # Use multipart form data for file upload
                files = {
                    'file': (os.path.basename(media_file_path), file_content, mime_type)
                }
                data = {
                    'messaging_product': 'whatsapp',
                    'type': media_type
                }
                
                response = await self.http_client.post(
                    url, 
                    headers=headers, 
                    files=files, 
                    data=data
                )
                
                print(f"🔊 Upload response status: {response.status_code}")
                print(f"🔊 Upload response body: {response.text}")
                
                if response.status_code == 200:
                    result = response.json()
                    media_id = result.get('id')
                    
                    if media_id:
                        print(f"✅ Media uploaded successfully. Media ID: {media_id}")
                        return media_id
                    else:
                        print("❌ No media ID returned from upload")
                        return None
                else:
                    print(f"❌ Upload failed: {response.status_code} - {response.text}")
                    return None
                    
            except httpx.HTTPError as e:
                print(f"❌ Error uploading media: {e}")
                return None
            except FileNotFoundError:
                print(f"❌ Media file not found: {media_file_path}")
                return None
    
    async def send_media_by_id(self, to_number: str, media_id: str, media_type: str = "audio") -> bool:
        """Send media message using media ID (async)"""
        async with self.api_semaphore:
            try:
                url = f"{self.base_url}/messages"
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": media_type,
                    media_type: {
                        "id": media_id
                    }
                }
                
                response = await self.http_client.post(url, headers=headers, json=data)
                
                print(f"📤 Media send response status: {response.status_code}")
                print(f"📤 Media send response body: {response.text}")
                
                if response.status_code == 200:
                    print(f"✅ Media message sent to {to_number}")
                    return True
                else:
                    print(f"❌ Media send error: {response.status_code} - {response.text}")
                    return False
                
            except httpx.HTTPError as e:
                print(f"❌ Error sending media by ID: {e}")
                return False
    
    async def get_media_url(self, media_id: str) -> Optional[str]:
        """Get media URL from media ID (async)"""
        async with self.api_semaphore:
            try:
                url = f"https://graph.facebook.com/{media_id}"
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }
                
                response = await self.http_client.get(url, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                return result.get('url')
                
            except httpx.HTTPError as e:
                print(f"❌ Error getting media URL: {e}")
                return None
    
    async def download_media(self, media_url: str, file_path: str) -> bool:
        """Download media from WhatsApp servers (async)"""
        async with self.api_semaphore:
            try:
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }
                
                response = await self.http_client.get(media_url, headers=headers)
                response.raise_for_status()
                
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                
                print(f"✅ Media downloaded to {file_path}")
                return True
                
            except httpx.HTTPError as e:
                print(f"❌ Error downloading media: {e}")
                return False
            except IOError as e:
                print(f"❌ Error writing file: {e}")
                return False
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """Verify webhook for WhatsApp"""
        if mode == "subscribe" and token == self.verify_token:
            print("✅ Webhook verified successfully")
            return challenge
        else:
            print("❌ Webhook verification failed")
            return None
    
    def process_webhook_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook data from WhatsApp"""
        try:
            print(f"🔍 Raw webhook data: {webhook_data}")
            
            if 'entry' not in webhook_data:
                print("❌ No 'entry' in webhook data")
                return {}
            
            entry = webhook_data['entry'][0]
            print(f"🔍 Entry data: {entry}")
            
            if 'changes' not in entry:
                print("❌ No 'changes' in entry")
                return {}
            
            change = entry['changes'][0]
            print(f"🔍 Change data: {change}")
            
            if 'value' not in change or 'messages' not in change['value']:
                print("❌ No 'value' or 'messages' in change")
                return {}
            
            messages = change['value']['messages']
            print(f"🔍 Messages: {messages}")
            
            if not messages:
                print("❌ No messages found")
                return {}
            
            message = messages[0]
            print(f"🔍 First message: {message}")
            
            # Extract message data
            message_data = {
                'from_number': message.get('from', ''),
                'message_id': message.get('id', ''),
                'timestamp': message.get('timestamp', ''),
                'type': message.get('type', 'text'),
                'text': '',
                'media_url': '',
                'media_id': ''
            }
            
            # Extract text content
            if 'text' in message:
                message_data['text'] = message['text'].get('body', '')
                print(f"🔍 Text content: {message_data['text']}")
            
            # Extract media content
            if 'audio' in message:
                message_data['media_id'] = message['audio'].get('id', '')
                message_data['media_url'] = message['audio'].get('link', '')
                print(f"🔍 Audio media_id: {message_data['media_id']}")
                print(f"🔍 Audio media_url: {message_data['media_url']}")
            elif 'image' in message:
                message_data['media_id'] = message['image'].get('id', '')
                message_data['media_url'] = message['image'].get('link', '')
                print(f"🔍 Image media_id: {message_data['media_id']}")
            elif 'document' in message:
                message_data['media_id'] = message['document'].get('id', '')
                message_data['media_url'] = message['document'].get('link', '')
                print(f"🔍 Document media_id: {message_data['media_id']}")
            
            print(f"🔍 Final message_data: {message_data}")
            return message_data
            
        except Exception as e:
            print(f"❌ Error processing webhook data: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _is_message_processed(self, message_id: str) -> bool:
        """Check if a message has already been processed"""
        if not message_id:
            return False
        
        # Cleanup old messages
        current_time = time.time()
        expired_ids = [
            msg_id for msg_id, timestamp in self.processed_messages.items()
            if current_time - timestamp > self.message_ttl
        ]
        for msg_id in expired_ids:
            del self.processed_messages[msg_id]
        
        # Check if message was already processed
        if message_id in self.processed_messages:
            print(f"⚠️ Message {message_id} already processed, skipping duplicate")
            return True
        
        return False
    
    def _mark_message_processed(self, message_id: str):
        """Mark a message as processed"""
        if message_id:
            self.processed_messages[message_id] = time.time()
            print(f"✅ Marked message {message_id} as processed")
    
    async def _get_patient_lock(self, patient_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific patient"""
        # Use threading lock for synchronous dictionary access
        with self.locks_lock:
            if patient_id not in self.patient_locks:
                self.patient_locks[patient_id] = asyncio.Lock()
            return self.patient_locks[patient_id]
    
    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook data from WhatsApp"""
        try:
            # Process the webhook data
            message_data = self.process_webhook_data(webhook_data)
            
            if not message_data:
                return {
                    "success": False,
                    "message": "No valid message data found"
                }
            
            message_id = message_data.get('message_id', '')
            from_number = message_data.get('from_number', '')
            
            # Check for duplicate messages
            if self._is_message_processed(message_id):
                return {
                    "success": True,
                    "message_data": message_data,
                    "processed": False,
                    "reason": "duplicate"
                }
            
            print(f"📱 Received WhatsApp message: {message_data}")
            
            # Mark message as read (non-blocking)
            if message_id:
                await self.mark_message_as_read(message_id)
            
            # Process the message based on type
            message_type = message_data.get('type', 'text')
            
            if message_type == 'audio':
                print(f"🎵 Processing voice message from {from_number}")
                
                # Get patient-specific lock to prevent concurrent processing
                patient_lock = await self._get_patient_lock(from_number)
                
                async with patient_lock:
                    # Double-check after acquiring lock (in case another request processed it)
                    if self._is_message_processed(message_id):
                        print(f"⚠️ Message {message_id} was processed by another request, skipping")
                        return {
                            "success": True,
                            "message_data": message_data,
                            "processed": False,
                            "reason": "duplicate_after_lock"
                        }
                    
                    # Mark as processed BEFORE processing (to prevent race conditions)
                    self._mark_message_processed(message_id)
                    
                    # Handle voice message
                    await self.handle_voice_message(message_data)
            else:
                print(f"❓ Ignoring non-voice message type: {message_type}")
                # Mark non-voice messages as processed too
                if message_id:
                    self._mark_message_processed(message_id)
            
            return {
                "success": True,
                "message_data": message_data,
                "processed": True
            }
                
        except Exception as e:
            print(f"❌ Error handling webhook: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _should_send_response(self, patient_id: str, message_id: str) -> bool:
        """Check if we should send a response (prevent duplicate responses)"""
        current_time = time.time()
        
        # Check if we recently sent a response to this patient
        if patient_id in self.last_response:
            last_msg_id, last_timestamp = self.last_response[patient_id]
            
            # If same message or very recent (within 2 seconds), don't send
            if last_msg_id == message_id or (current_time - last_timestamp) < 2.0:
                print(f"⚠️ Skipping duplicate response for patient {patient_id}, message {message_id}")
                return False
        
        # Update last response tracking
        self.last_response[patient_id] = (message_id, current_time)
        
        # Cleanup old entries (older than 5 minutes)
        expired_patients = [
            pid for pid, (_, ts) in self.last_response.items()
            if current_time - ts > 300
        ]
        for pid in expired_patients:
            del self.last_response[pid]
        
        return True
    
    async def handle_voice_message(self, message_data: Dict[str, Any]):
        """Handle incoming voice message"""
        try:
            from_number = message_data.get('from_number', '')
            media_id = message_data.get('media_id', '')
            message_id = message_data.get('message_id', '')
            
            print(f"🎵 Starting voice message processing for {from_number}")
            print(f"🎵 Media ID: {media_id}, Message ID: {message_id}")
            
            if not media_id:
                print("❌ No media ID found in voice message")
                return
            
            # Check if we should send a response (prevent duplicates)
            if not self._should_send_response(from_number, message_id):
                print(f"⚠️ Skipping response for {from_number} - duplicate detected")
                return
            
            # Download the voice message
            print(f"🎵 Getting media URL for ID: {media_id}")
            media_url = await self.get_media_url(media_id)
            print(f"🎵 Media URL: {media_url}")
            
            if not media_url:
                print("❌ Could not get media URL")
                return
            
            # Download audio file
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
                if await self.download_media(media_url, tmp_file.name):
                    print(f"✅ Downloaded voice message to {tmp_file.name}")
                    
                    # Process voice message using your voice processing
                    from app.voice_processing import voice_processor
                    from app.intelligent_conversation_engine import intelligent_conversation_engine
                    
                    # Convert speech to text
                    text = await voice_processor.speech_to_text(tmp_file.name)
                    print(f"🎤 Transcribed text: {text}")
                    
                    if text:
                        # Process conversation
                        conversation_result = await intelligent_conversation_engine.process_patient_response(
                            patient_text=text,
                            patient_id=from_number
                        )
                        
                        # Get AI response
                        response_text = conversation_result.get('response_text', 'I understand. Please tell me more.')
                        print(f"🤖 AI Response: {response_text}")
                        
                        # Check if EMR generation is needed
                        action = conversation_result.get('action', 'continue_conversation')
                        print(f"🔍 Action from conversation result: {action}")
                        if action == 'generate_emr':
                            print("🚨 Generating EMR for completed conversation...")
                            try:
                                emr_result = await intelligent_conversation_engine.generate_emr(from_number)
                                if emr_result:
                                    print("✅ EMR generated successfully")
                                else:
                                    print("❌ EMR generation failed")
                            except Exception as e:
                                print(f"❌ EMR generation error: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Convert response to speech
                        audio_file = await voice_processor.text_to_speech(response_text)
                        print(f"🔊 Generated audio type: {type(audio_file)}")
                        print(f"🔊 Generated audio preview: {str(audio_file)[:100]}...")
                        
                        # Send voice response back
                        if audio_file and isinstance(audio_file, str) and audio_file.endswith(('.wav', '.mp3', '.ogg')):
                            # Upload audio to WhatsApp
                            print(f"🔊 Uploading audio file: {audio_file}")
                            uploaded_media_id = await self.upload_media(audio_file, "audio")
                            if uploaded_media_id:
                                await self.send_media_by_id(from_number, uploaded_media_id, "audio")
                                print(f"✅ Sent voice response to {from_number}")
                            else:
                                print(f"❌ Failed to upload audio, no response sent")
                        else:
                            print(f"❌ Audio file invalid, no response sent")
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
                else:
                    print("❌ Failed to download voice message")
                    
        except Exception as e:
            print(f"❌ Error handling voice message: {e}")
            import traceback
            traceback.print_exc()
    
    
    async def mark_message_as_read(self, message_id: str) -> bool:
        """Mark a message as read (async)"""
        # Don't block on read receipts - fire and forget
        try:
            url = f"{self.base_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }
            
            # Use asyncio.create_task to not block
            asyncio.create_task(self._mark_read_async(url, headers, data, message_id))
            return True
            
        except Exception as e:
            print(f"❌ Error scheduling mark as read: {e}")
            return False
    
    async def _mark_read_async(self, url: str, headers: dict, data: dict, message_id: str):
        """Async helper to mark message as read"""
        async with self.api_semaphore:
            try:
                response = await self.http_client.post(url, headers=headers, json=data)
                response.raise_for_status()
                print(f"✅ Message {message_id} marked as read")
            except httpx.HTTPError as e:
                print(f"❌ Error marking message as read: {e}")
    

# Global instance
whatsapp_service = MetaWhatsAppService()
