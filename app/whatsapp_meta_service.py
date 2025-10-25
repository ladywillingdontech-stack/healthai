"""
Meta WhatsApp Business API Integration
Handles sending and receiving WhatsApp messages using Meta's official API
"""

import requests
import json
import os
from typing import Optional, Dict, Any
from app.config import settings

class MetaWhatsAppService:
    def __init__(self):
        self.access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.verify_token = settings.whatsapp_verify_token
        # Let WhatsApp decide the API version automatically
        self.base_url = f"https://graph.facebook.com/{self.phone_number_id}"
        
    
    def send_voice_message(self, to_number: str, audio_url: str) -> bool:
        """Send a voice message via WhatsApp"""
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
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print(f"✅ Voice message sent to {to_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending voice message: {e}")
            return False
    
    def send_media_message(self, to_number: str, media_url: str, media_type: str = "audio") -> bool:
        """Send media message (audio, image, document) via WhatsApp"""
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
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print(f"✅ {media_type} message sent to {to_number}")
            return True
            
        except requests.exceptions.RequestException as e:
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
    
    def upload_media(self, media_file_path: str, media_type: str = "audio") -> Optional[str]:
        """Upload media file to WhatsApp servers and get media ID"""
        try:
            url = f"https://graph.facebook.com/{self.phone_number_id}/media"
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            with open(media_file_path, 'rb') as file:
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
                
                files = {
                    'file': (os.path.basename(media_file_path), file, mime_type)
                }
                data = {
                    'messaging_product': 'whatsapp',
                    'type': media_type
                }
                
                response = requests.post(url, headers=headers, files=files, data=data)
                
                print(f"🔊 Upload response status: {response.status_code}")
                print(f"🔊 Upload response headers: {dict(response.headers)}")
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
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Error uploading media: {e}")
            return None
        except FileNotFoundError:
            print(f"❌ Media file not found: {media_file_path}")
            return None
    
    def send_media_by_id(self, to_number: str, media_id: str, media_type: str = "audio") -> bool:
        """Send media message using media ID"""
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
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print(f"✅ Media message sent to {to_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending media by ID: {e}")
            return False
    
    def get_media_url(self, media_id: str) -> Optional[str]:
        """Get media URL from media ID"""
        try:
            url = f"https://graph.facebook.com/{media_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            return result.get('url')
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting media URL: {e}")
            return None
    
    def download_media(self, media_url: str, file_path: str) -> bool:
        """Download media from WhatsApp servers"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = requests.get(media_url, headers=headers)
            response.raise_for_status()
            
            with open(file_path, 'wb') as file:
                file.write(response.content)
            
            print(f"✅ Media downloaded to {file_path}")
            return True
            
        except requests.exceptions.RequestException as e:
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
    
    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook data from WhatsApp"""
        try:
            # Process the webhook data
            message_data = self.process_webhook_data(webhook_data)
            
            if message_data:
                print(f"📱 Received WhatsApp message: {message_data}")
                
                # Mark message as read
                if message_data.get('message_id'):
                    self.mark_message_as_read(message_data['message_id'])
                
                # Process the message based on type
                from_number = message_data.get('from_number', '')
                message_type = message_data.get('type', 'text')
                
                if message_type == 'audio':
                    print(f"🎵 Processing voice message from {from_number}")
                    # Handle voice message
                    await self.handle_voice_message(message_data)
                else:
                    print(f"❓ Ignoring non-voice message type: {message_type}")
                
                return {
                    "success": True,
                    "message_data": message_data,
                    "processed": True
                }
            else:
                return {
                    "success": False,
                    "message": "No valid message data found"
                }
                
        except Exception as e:
            print(f"❌ Error handling webhook: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_voice_message(self, message_data: Dict[str, Any]):
        """Handle incoming voice message"""
        try:
            from_number = message_data.get('from_number', '')
            media_id = message_data.get('media_id', '')
            
            print(f"🎵 Starting voice message processing for {from_number}")
            print(f"🎵 Media ID: {media_id}")
            
            if not media_id:
                print("❌ No media ID found in voice message")
                return
            
            # Download the voice message
            print(f"🎵 Getting media URL for ID: {media_id}")
            media_url = self.get_media_url(media_id)
            print(f"🎵 Media URL: {media_url}")
            
            if not media_url:
                print("❌ Could not get media URL")
                return
            
            # Download audio file
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
                if self.download_media(media_url, tmp_file.name):
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
                        
                        # Convert response to speech
                        audio_file = voice_processor.text_to_speech(response_text)
                        print(f"🔊 Generated audio type: {type(audio_file)}")
                        print(f"🔊 Generated audio preview: {str(audio_file)[:100]}...")
                        
                        # Send voice response back
                        if audio_file and isinstance(audio_file, str) and audio_file.endswith(('.wav', '.mp3', '.ogg')):
                            # Upload audio to WhatsApp
                            print(f"🔊 Uploading audio file: {audio_file}")
                            uploaded_media_id = self.upload_media(audio_file, "audio")
                            if uploaded_media_id:
                                self.send_media_by_id(from_number, uploaded_media_id, "audio")
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
    
    
    def mark_message_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
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
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print(f"✅ Message {message_id} marked as read")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error marking message as read: {e}")
            return False
    

# Global instance
whatsapp_service = MetaWhatsAppService()









