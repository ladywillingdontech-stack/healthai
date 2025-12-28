"""
Roman Urdu to Urdu Script Converter
Converts Roman Urdu (English transliteration) to proper Urdu script for better TTS
"""
import re
import openai
from typing import Optional
from app.config import settings


class UrduConverter:
    """Convert Roman Urdu text to Urdu script"""
    
    def __init__(self):
        # Common Roman Urdu to Urdu mappings
        self.transliteration_map = {
            # Pronouns and common words
            'aap': 'آپ',
            'ap': 'آپ',
            'aapka': 'آپ کا',
            'apka': 'آپ کا',
            'aapki': 'آپ کی',
            'apki': 'آپ کی',
            'aapke': 'آپ کے',
            'apke': 'آپ کے',
            'mera': 'میرا',
            'meri': 'میری',
            'mere': 'میرے',
            'tumhara': 'تمہارا',
            'tumhari': 'تمہاری',
            'tumhare': 'تمہارے',
            'hamara': 'ہمارا',
            'hamari': 'ہماری',
            'hamare': 'ہمارے',
            
            # Question words
            'kya': 'کیا',
            'kyaa': 'کیا',
            'konsa': 'کونسا',
            'konsi': 'کونسی',
            'konse': 'کونسے',
            'kaun': 'کون',
            'kaunsi': 'کونسی',
            'kaunsa': 'کونسا',
            'kahan': 'کہاں',
            'kab': 'کب',
            'kyun': 'کیوں',
            'kaise': 'کیسے',
            'kitna': 'کتنا',
            'kitni': 'کتنی',
            'kitne': 'کتنے',
            
            # Common verbs
            'hai': 'ہے',
            'hain': 'ہیں',
            'ho': 'ہو',
            'hoa': 'ہوا',
            'hui': 'ہوئی',
            'hue': 'ہوئے',
            'hoga': 'ہوگا',
            'hogi': 'ہوگی',
            'honge': 'ہوں گے',
            'karo': 'کرو',
            'karein': 'کریں',
            'karta': 'کرتا',
            'karti': 'کرتی',
            'karte': 'کرتے',
            'kiya': 'کیا',
            'ki': 'کی',
            'ke': 'کے',
            'ko': 'کو',
            'ka': 'کا',
            
            # Prepositions
            'mein': 'میں',
            'se': 'سے',
            'tak': 'تک',
            'par': 'پر',
            'ke': 'کے',
            'ka': 'کا',
            'ki': 'کی',
            'ko': 'کو',
            'ne': 'نے',
            
            # Conjunctions
            'aur': 'اور',
            'ya': 'یا',
            'lekin': 'لیکن',
            'magar': 'مگر',
            'agar': 'اگر',
            'to': 'تو',
            'tou': 'تو',
            'phir': 'پھر',
            'bhi': 'بھی',
            
            # Negations
            'nahi': 'نہیں',
            'nahin': 'نہیں',
            'na': 'نا',
            'mat': 'مت',
            'naheen': 'نہیں',
            
            # Time words
            'ab': 'اب',
            'abhi': 'ابھی',
            'kal': 'کل',
            'parson': 'پرسوں',
            'aaj': 'آج',
            'din': 'دن',
            'raat': 'رات',
            'subah': 'صبح',
            'dopahar': 'دوپہر',
            'shaam': 'شام',
            
            # Medical terms
            'dard': 'درد',
            'takleef': 'تکلیف',
            'bimari': 'بیماری',
            'alamat': 'علامات',
            'bukhar': 'بخار',
            'khansi': 'کھانسی',
            'ulti': 'اُلٹی',
            'khoon': 'خون',
            'doktor': 'ڈاکٹر',
            'doctor': 'ڈاکٹر',
            'hospital': 'ہسپتال',
            'dawai': 'دوائی',
            'ilaj': 'علاج',
            'test': 'ٹیسٹ',
            'blood': 'بلڈ',
            'pressure': 'پریشر',
            'sugar': 'شوگر',
            
            # Common phrases
            'theek hai': 'ٹھیک ہے',
            'accha': 'اچھا',
            'bilkul': 'بالکل',
            'zaroor': 'ضرور',
            'shukriya': 'شکریہ',
            'maaf': 'معاف',
            'kijiye': 'کیجیے',
            'karein': 'کریں',
            'bataiye': 'بتائیے',
            'batao': 'بتاؤ',
            'batayein': 'بتائیں',
            
            # Greetings
            'assalam': 'السلام',
            'alaikum': 'علیکم',
            'salam': 'سلام',
            'adaab': 'آداب',
            
            # Numbers (basic)
            'ek': 'ایک',
            'do': 'دو',
            'teen': 'تین',
            'char': 'چار',
            'paanch': 'پانچ',
            'chhah': 'چھ',
            'saat': 'سات',
            'aath': 'آٹھ',
            'nau': 'نو',
            'das': 'دس',
        }
        
    def convert_to_urdu(self, text: str, use_ai: bool = True) -> str:
        """
        Convert Roman Urdu to Urdu script
        Uses pattern matching first, then AI for better accuracy
        """
        if not text or not text.strip():
            return text
        
        # Check if text is already in Urdu (contains Urdu characters)
        if self._is_urdu_text(text):
            return text
        
        # Try AI conversion first for better accuracy
        if use_ai and settings.openai_api_key and len(settings.openai_api_key) > 10:
            urdu_text = self._convert_with_ai(text)
            if urdu_text and urdu_text != text:
                return urdu_text
        
        # Fallback to pattern matching
        return self._convert_with_patterns(text)
    
    def _is_urdu_text(self, text: str) -> bool:
        """Check if text already contains Urdu characters"""
        # Urdu Unicode range: \u0600-\u06FF
        urdu_pattern = re.compile(r'[\u0600-\u06FF]')
        return bool(urdu_pattern.search(text))
    
    def _convert_with_ai(self, text: str) -> str:
        """Use GPT-4 to convert Roman Urdu to Urdu script with improved accuracy"""
        try:
            # Skip AI conversion for very short text or if it's mostly numbers/special chars
            if len(text.strip()) < 5:
                return text
            
            prompt = f"""You are an expert Urdu linguist. Convert this Roman Urdu (English transliteration) text to proper, grammatically correct Urdu script.

CRITICAL RULES:
1. Use proper Urdu grammar and correct word forms (e.g., "آپ کا" not "آپکا", "آپ کی" not "آپکی")
2. Use correct Urdu diacritics and proper letter combinations
3. Preserve numbers as digits (e.g., "25" stays "25")
4. Keep English medical/technical terms as-is: CNIC, Hb, ultrasound, test, BP, sugar, etc.
5. Use proper Urdu punctuation marks (؟ for questions, ، for commas)
6. Ensure proper spacing between words
7. Use correct Urdu verb forms and conjugations
8. Convert ALL Roman Urdu words to proper Urdu script - do not leave any Roman Urdu words unconverted

Text to convert: "{text}"

Examples of correct conversion:
- "Aapka naam kya hai?" → "آپ کا نام کیا ہے؟"
- "Aapki umar kitni hai?" → "آپ کی عمر کتنی ہے؟"
- "Mera naam Sadia hai" → "میرا نام سعدیہ ہے"
- "Kya aapko dard hai?" → "کیا آپ کو درد ہے؟"
- "Aapne test karwaya?" → "آپ نے ٹیسٹ کروایا؟"

Now convert this text accurately: "{text}"

Return ONLY the converted Urdu text, nothing else. No explanations, no quotes, just the Urdu text."""
            
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert Urdu linguist specializing in converting Roman Urdu (English transliteration) to proper, grammatically correct Urdu script. You understand Urdu grammar, proper word forms, diacritics, and punctuation. You always produce accurate, natural-sounding Urdu text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Lower temperature for more consistent, accurate results
                max_tokens=1000
            )
            
            urdu_text = response.choices[0].message.content.strip()
            
            # Clean up the response - remove quotes, prefixes, etc.
            urdu_text = urdu_text.strip('"').strip("'").strip()
            
            # Remove common prefixes that GPT might add
            prefixes_to_remove = ["Output:", "Converted:", "Urdu text:", "Result:", "Answer:"]
            for prefix in prefixes_to_remove:
                if urdu_text.lower().startswith(prefix.lower()):
                    urdu_text = urdu_text[len(prefix):].strip().strip('"').strip("'").strip()
            
            # If there's a colon, take everything after it
            if ':' in urdu_text and not self._is_urdu_text(urdu_text.split(':')[0]):
                parts = urdu_text.split(':', 1)
                if len(parts) > 1:
                    urdu_text = parts[1].strip().strip('"').strip("'").strip()
            
            # Verify it's actually Urdu (contains Urdu characters)
            if self._is_urdu_text(urdu_text):
                print(f"✅ Converted to Urdu via AI: {urdu_text[:100]}...")
                return urdu_text
            else:
                print(f"⚠️ AI returned text without Urdu characters, using pattern matching")
                return text
                
        except Exception as e:
            print(f"⚠️ AI conversion failed: {e}, using pattern matching")
            return text
    
    def _convert_with_patterns(self, text: str) -> str:
        """Convert using pattern matching (fallback method)"""
        converted_text = text
        
        # Sort by length (longest first) to avoid partial matches
        sorted_map = sorted(self.transliteration_map.items(), key=lambda x: len(x[0]), reverse=True)
        
        for roman, urdu in sorted_map:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(roman) + r'\b'
            converted_text = re.sub(pattern, urdu, converted_text, flags=re.IGNORECASE)
        
        return converted_text


# Initialize converter
urdu_converter = UrduConverter()
