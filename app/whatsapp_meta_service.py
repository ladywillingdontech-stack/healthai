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
        self.api_version = settings.whatsapp_api_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        
    def send_text_message(self, to_number: str, message: str) -> bool:
        """Send a text message via WhatsApp"""
        try:
            url = f"{self.base_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {
                    "body": message
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print(f"✅ Text message sent to {to_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending text message: {e}")
            return False
    
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
            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/media"
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            with open(media_file_path, 'rb') as file:
                files = {
                    'file': (os.path.basename(media_file_path), file, f'audio/{media_type}')
                }
                data = {
                    'messaging_product': 'whatsapp',
                    'type': media_type
                }
                
                response = requests.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                
                result = response.json()
                media_id = result.get('id')
                
                if media_id:
                    print(f"✅ Media uploaded successfully. Media ID: {media_id}")
                    return media_id
                else:
                    print("❌ No media ID returned from upload")
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
            url = f"https://graph.facebook.com/{self.api_version}/{media_id}"
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
            if 'entry' not in webhook_data:
                return {}
            
            entry = webhook_data['entry'][0]
            if 'changes' not in entry:
                return {}
            
            change = entry['changes'][0]
            if 'value' not in change or 'messages' not in change['value']:
                return {}
            
            messages = change['value']['messages']
            if not messages:
                return {}
            
            message = messages[0]
            
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
            
            # Extract media content
            if 'audio' in message:
                message_data['media_id'] = message['audio'].get('id', '')
                message_data['media_url'] = message['audio'].get('link', '')
            elif 'image' in message:
                message_data['media_id'] = message['image'].get('id', '')
                message_data['media_url'] = message['image'].get('link', '')
            elif 'document' in message:
                message_data['media_id'] = message['document'].get('id', '')
                message_data['media_url'] = message['document'].get('link', '')
            
            return message_data
            
        except Exception as e:
            print(f"❌ Error processing webhook data: {e}")
            return {}
    
    def handle_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook data from WhatsApp"""
        try:
            # Process the webhook data
            message_data = self.process_webhook_data(webhook_data)
            
            if message_data:
                # Mark message as read
                if message_data.get('message_id'):
                    self.mark_message_as_read(message_data['message_id'])
                
                # Process the message (integrate with your conversation engine)
                # This is where you'd call your intelligent_conversation_engine
                
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
    
    def send_message(self, phone_number: str, message: str) -> bool:
        """Send a WhatsApp message"""
        return self.send_text_message(phone_number, message)

# Global instance
whatsapp_service = MetaWhatsAppService()









