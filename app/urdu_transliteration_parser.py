import PyPDF2
import re
from typing import List, Dict, Any
from app.models import ChromaQuestion


class UrduTransliterationParser:
    """Parser for Urdu questions written in English transliteration"""
    
    def __init__(self):
        # Common Urdu transliteration patterns
        self.question_patterns = [
            r'^\d+\.\s*"([^"]+)"',  # Numbered questions in quotes
            r'^\d+\.\s*([^?]+)\?',  # Numbered questions ending with ?
            r'^[Aa]p\s+[^?]*\?',  # Questions starting with "Ap"
            r'^[Kk]ya\s+[^?]*\?',  # Questions starting with "Kya"
            r'^[Aa]ap\s+[^?]*\?',  # Questions starting with "Aap"
            r'^Please\s+[^?]*\?',  # Questions starting with "Please"
            r'^[Aa]pna\s+[^?]*\?',  # Questions starting with "Apna"
            r'^[Aa]pne\s+[^?]*\?',  # Questions starting with "Apne"
            r'^[Kk]ya\s+[Aa]ap\s+[^?]*\?',  # Questions starting with "Kya aap"
            r'^[Aa]ap\s+[Kk]ya\s+[^?]*\?',  # Questions starting with "Aap kya"
        ]
        
        # Transliteration mapping for common Urdu words
        self.transliteration_map = {
            # Basic words
            'aap': 'آپ',
            'ap': 'آپ',
            'kya': 'کیا',
            'hai': 'ہے',
            'hain': 'ہیں',
            'ka': 'کا',
            'ki': 'کی',
            'ke': 'کے',
            'ko': 'کو',
            'mein': 'میں',
            'se': 'سے',
            'tak': 'تک',
            'ya': 'یا',
            'aur': 'اور',
            'bhi': 'بھی',
            'nahi': 'نہیں',
            'nahin': 'نہیں',
            'tou': 'تو',
            'agar': 'اگر',
            'to': 'تو',
            'abhi': 'ابھی',
            'kitna': 'کتنا',
            'kitni': 'کتنی',
            'kya': 'کیا',
            'konsi': 'کونسی',
            'konsa': 'کونسا',
            'kahan': 'کہاں',
            'kab': 'کب',
            'kyun': 'کیوں',
            'kaise': 'کیسے',
            
            # Medical terms
            'dard': 'درد',
            'takleef': 'تکلیف',
            'bimari': 'بیماری',
            'alamat': 'علامات',
            'symptom': 'علامت',
            'test': 'ٹیسٹ',
            'blood': 'بلڈ',
            'pressure': 'پریشر',
            'sugar': 'شوگر',
            'diabetes': 'ذیابیطس',
            'heart': 'دل',
            'chest': 'سینہ',
            'head': 'سر',
            'stomach': 'پیٹ',
            'back': 'کمر',
            'joint': 'جوڑ',
            'fever': 'بخار',
            'cough': 'کھانسی',
            'breath': 'سانس',
            'pain': 'درد',
            'ache': 'تکلیف',
            'fatigue': 'تھکاوٹ',
            'weakness': 'کمزوری',
            'sleep': 'نیند',
            'hunger': 'بھوک',
            'thirst': 'پیاس',
            'urine': 'پیشاب',
            'stool': 'پاخانہ',
            'vomit': 'الٹی',
            'nausea': 'متلی',
            'dizziness': 'چکر',
            'fainting': 'بے ہوشی',
            'bleeding': 'خون بہنا',
            'swelling': 'سوجن',
            'rash': 'خارش',
            'itch': 'کھجلی',
            'burning': 'جلن',
            'numbness': 'سن',
            'tingling': 'جھنجھناہٹ',
            
            # Body parts
            'sar': 'سر',
            'aankh': 'آنکھ',
            'kaan': 'کان',
            'naak': 'ناک',
            'muh': 'منہ',
            'dant': 'دانت',
            'gala': 'گلا',
            'gardan': 'گردن',
            'kandha': 'کندھا',
            'bazu': 'بازو',
            'hath': 'ہاتھ',
            'ungli': 'انگلی',
            'chhati': 'چھاتی',
            'pet': 'پیٹ',
            'kamar': 'کمر',
            'jangh': 'ران',
            'ghutna': 'گھٹنا',
            'paon': 'پاؤں',
            'pair': 'پیر',
            
            # Family terms
            'shohar': 'شوہر',
            'biwi': 'بیوی',
            'bacha': 'بچہ',
            'bachay': 'بچے',
            'beta': 'بیٹا',
            'beti': 'بیٹی',
            'maa': 'ماں',
            'baap': 'باپ',
            'dada': 'دادا',
            'dadi': 'دادی',
            'nana': 'نانا',
            'nani': 'نانی',
            'bhai': 'بھائی',
            'behen': 'بہن',
            'chacha': 'چچا',
            'chachi': 'چچی',
            'mama': 'ماما',
            'mami': 'مامی',
            'phupho': 'پھوپھو',
            'phupha': 'پھوپھا',
            'khala': 'خالہ',
            'khalu': 'خالو',
            'bua': 'بوا',
            'fufa': 'فوفا',
            
            # Time and numbers
            'din': 'دن',
            'raat': 'رات',
            'subah': 'صبح',
            'dopahar': 'دوپہر',
            'shaam': 'شام',
            'hafte': 'ہفتے',
            'mahine': 'مہینے',
            'saal': 'سال',
            'pehle': 'پہلے',
            'baad': 'بعد',
            'abhi': 'ابھی',
            'kal': 'کل',
            'parson': 'پرسوں',
            'aaj': 'آج',
            
            # Common phrases
            'theek hai': 'ٹھیک ہے',
            'accha': 'اچھا',
            'buri': 'بری',
            'zada': 'زیادہ',
            'kam': 'کم',
            'bohot': 'بہت',
            'thoda': 'تھوڑا',
            'bilkul': 'بالکل',
            'zaroor': 'ضرور',
            'shayad': 'شاید',
            'mumkin': 'ممکن',
            'imkaan': 'امکان',
        }
        
        # Alert keywords in transliteration
        self.alert_keywords = {
            'red': [
                'chest pain', 'sine mein dard', 'breathlessness', 'saans lene mein mushkil',
                'fainting', 'be hoshi', 'severe bleeding', 'shadeed khoon bahna',
                'heart attack', 'dil ka dora', 'stroke', 'falaj', 'emergency', 'emergency'
            ],
            'yellow': [
                'mild', 'halka', 'headache', 'sar dard', 'cough', 'khansi',
                'fatigue', 'thakawat', 'fever', 'bukhar', 'discomfort', 'takleef'
            ]
        }
        
        # Question type keywords
        self.question_type_keywords = {
            'onboarding': [
                'naam', 'name', 'shanaakhti', 'identity', 'card', 'number',
                'jamat', 'education', 'ilaqa', 'area', 'kaam', 'work',
                'umar', 'age', 'shaadi', 'marriage', 'bachay', 'children'
            ],
            'demographic': [
                'gender', 'jins', 'male', 'mard', 'female', 'aurat', 'khawateen',
                'children', 'bachay', 'occupation', 'pesha', 'education', 'taleem',
                'income', 'aamadni', 'marital', 'shaadi', 'family', 'khandan'
            ],
            'symptom': [
                'pain', 'dard', 'ache', 'takleef', 'fever', 'bukhar', 'cough', 'khansi',
                'symptom', 'alamat', 'problem', 'masla', 'condition', 'halat',
                'bimari', 'disease', 'illness', 'sick', 'patient'
            ]
        }

    def parse_pdf(self, pdf_path: str) -> List[ChromaQuestion]:
        """Parse PDF and extract questions with transliteration handling"""
        questions = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    page_questions = self._extract_questions_from_text(text, page_num)
                    questions.extend(page_questions)
                    
        except Exception as e:
            print(f"Error reading PDF: {e}")
            
        return questions

    def _extract_questions_from_text(self, text: str, page_num: int) -> List[ChromaQuestion]:
        """Extract questions from text by reconstructing broken lines"""
        questions = []
        lines = text.split('\n')
        
        # Reconstruct text by joining words that are on separate lines
        reconstructed_text = ""
        current_question = ""
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check if this line starts a new question
            if (line.startswith('Please') or 
                line.startswith('Ap') or 
                line.startswith('Aap') or 
                line.startswith('Kya') or
                line.startswith('●')):
                
                # Save previous question if it exists
                if current_question.strip():
                    question_text = current_question.strip()
                    if '?' in question_text or len(question_text) > 10:
                        question_data = self._create_question_data(question_text, page_num, i)
                        questions.append(question_data)
                
                # Start new question
                if line.startswith('●'):
                    current_question = ""
                else:
                    current_question = line + " "
            else:
                # Continue current question
                current_question += line + " "
        
        # Don't forget the last question
        if current_question.strip():
            question_text = current_question.strip()
            if '?' in question_text or len(question_text) > 10:
                question_data = self._create_question_data(question_text, page_num, len(lines))
                questions.append(question_data)
        
        return questions

    def _convert_to_urdu(self, text: str) -> str:
        """Convert English transliteration to Urdu text"""
        # Convert to lowercase for matching
        text_lower = text.lower()
        
        # Apply transliteration mapping
        for eng, urdu in self.transliteration_map.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(eng) + r'\b'
            text_lower = re.sub(pattern, urdu, text_lower, flags=re.IGNORECASE)
        
        return text_lower

    def _create_question_data(self, text: str, page_num: int, line_num: int) -> ChromaQuestion:
        """Create ChromaQuestion object with enhanced metadata extraction"""
        question_id = f"q_{page_num}_{line_num}_{hash(text) % 10000}"
        
        # Determine question type
        question_type = self._determine_question_type(text)
        
        # Determine alert level
        alert_flag = self._determine_alert_level(text)
        
        # Extract condition (for conditional questions)
        condition = self._extract_condition(text)
        
        # Extract symptom type
        symptom = self._extract_symptom_type(text)
        
        return ChromaQuestion(
            id=question_id,
            question_text=text,
            type=question_type,
            condition=condition,
            symptom=symptom,
            alert_flag=alert_flag
        )

    def _determine_question_type(self, text: str) -> str:
        """Determine question type based on content analysis"""
        text_lower = text.lower()
        
        # Check for demographic keywords
        for keyword in self.question_type_keywords['demographic']:
            if keyword.lower() in text_lower:
                return 'demographic'
        
        # Check for symptom keywords
        for keyword in self.question_type_keywords['symptom']:
            if keyword.lower() in text_lower:
                return 'symptom'
        
        # Check for onboarding keywords
        for keyword in self.question_type_keywords['onboarding']:
            if keyword.lower() in text_lower:
                return 'onboarding'
        
        # Default to onboarding if unclear
        return 'onboarding'

    def _determine_alert_level(self, text: str) -> str:
        """Determine alert level based on content analysis"""
        text_lower = text.lower()
        
        # Check for red alert keywords
        for keyword in self.alert_keywords['red']:
            if keyword.lower() in text_lower:
                return 'red'
        
        # Check for yellow alert keywords
        for keyword in self.alert_keywords['yellow']:
            if keyword.lower() in text_lower:
                return 'yellow'
        
        return 'none'

    def _extract_condition(self, text: str) -> str:
        """Extract conditional logic from question text"""
        text_lower = text.lower()
        
        # Look for conditional patterns
        if 'if' in text_lower and 'children' in text_lower:
            if '1' in text or 'one' in text_lower:
                return 'if_children=1'
            elif '2' in text or 'two' in text_lower:
                return 'if_children=2'
            elif '3' in text or 'three' in text_lower:
                return 'if_children=3'
        
        if 'if' in text_lower and 'pregnant' in text_lower:
            return 'if_pregnant=yes'
        
        if 'if' in text_lower and 'diabetes' in text_lower:
            return 'if_diabetes=yes'
        
        return None

    def _extract_symptom_type(self, text: str) -> str:
        """Extract specific symptom type from question text"""
        text_lower = text.lower()
        
        symptom_mapping = {
            'chest': 'chest_pain',
            'sine': 'chest_pain',
            'cough': 'cough',
            'khansi': 'cough',
            'head': 'headache',
            'sar': 'headache',
            'fever': 'fever',
            'bukhar': 'fever',
            'stomach': 'stomach_pain',
            'pet': 'stomach_pain',
            'back': 'back_pain',
            'kamar': 'back_pain',
            'joint': 'joint_pain',
            'jod': 'joint_pain'
        }
        
        for keyword, symptom in symptom_mapping.items():
            if keyword in text_lower:
                return symptom
        
        return None

    def validate_questions(self, questions: List[ChromaQuestion]) -> Dict[str, Any]:
        """Validate and provide statistics about parsed questions"""
        stats = {
            'total_questions': len(questions),
            'by_type': {},
            'by_alert': {},
            'with_conditions': 0,
            'with_symptoms': 0,
            'urdu_questions': 0,
            'transliterated_questions': 0
        }
        
        for question in questions:
            # Count by type
            q_type = question.type
            stats['by_type'][q_type] = stats['by_type'].get(q_type, 0) + 1
            
            # Count by alert level
            alert = question.alert_flag
            stats['by_alert'][alert] = stats['by_alert'].get(alert, 0) + 1
            
            # Count conditions and symptoms
            if question.condition:
                stats['with_conditions'] += 1
            if question.symptom:
                stats['with_symptoms'] += 1
            
            # Count language type
            if any('\u0600' <= char <= '\u06FF' for char in question.question_text):
                stats['urdu_questions'] += 1
            else:
                stats['transliterated_questions'] += 1
        
        return stats


# Enhanced Chroma DB setup with Urdu transliteration support
class UrduChromaDBSetup:
    def __init__(self):
        from app.chroma_setup import ChromaDBSetup
        self.base_setup = ChromaDBSetup()
        self.parser = UrduTransliterationParser()

    def setup_with_urdu_parsing(self, pdf_path: str) -> int:
        """Setup Chroma DB with Urdu transliteration parsing"""
        print("🔄 Parsing PDF with Urdu transliteration parser...")
        questions = self.parser.parse_pdf(pdf_path)
        
        if not questions:
            print("❌ No questions found in PDF")
            return 0
        
        # Validate questions
        stats = self.parser.validate_questions(questions)
        print(f"📊 Parsed {stats['total_questions']} questions:")
        print(f"   - By type: {stats['by_type']}")
        print(f"   - By alert: {stats['by_alert']}")
        print(f"   - With conditions: {stats['with_conditions']}")
        print(f"   - With symptoms: {stats['with_symptoms']}")
        print(f"   - Urdu: {stats['urdu_questions']}, Transliterated: {stats['transliterated_questions']}")
        
        # Show sample questions
        print("\n📝 Sample questions:")
        for i, q in enumerate(questions[:5]):
            print(f"   {i+1}. {q.question_text}")
        
        # Create embeddings
        print("🔄 Creating embeddings...")
        embeddings = self.base_setup.create_embeddings(questions)
        
        # Store in Chroma DB
        print("🔄 Storing in Chroma DB...")
        self.base_setup.store_questions_in_chroma(questions, embeddings)
        
        return len(questions)
    
    def get_questions_by_type(self, question_type: str) -> List[Dict]:
        """Get questions by type from Chroma DB"""
        return self.base_setup.get_questions_by_type(question_type)
