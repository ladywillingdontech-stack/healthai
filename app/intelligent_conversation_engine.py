import json
import openai
from datetime import datetime
from typing import Dict, Any, List
from app.firestore_service import FirestoreService
from app.config import settings

class IntelligentConversationEngine:
    def __init__(self):
        self.firestore_service = FirestoreService()
        # Configure OpenAI
        openai.api_key = settings.openai_api_key
    
    async def process_patient_response(self, patient_text: str, patient_id: str) -> Dict[str, Any]:
        """Main method to process patient responses intelligently"""
        
        try:
            # Get or create patient data
            patient_data = await self.firestore_service.get_patient(patient_id)
            if not patient_data:
                patient_data = self._initialize_patient_data(patient_id)
                await self.firestore_service.create_patient(patient_data)
            
            # Add current response to conversation history
            patient_data["conversation_history"].append({
                "patient_text": patient_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Extract information intelligently
            await self._extract_information_intelligently(patient_text, patient_data)
            
            # Determine next phase and response
            result = await self._determine_next_response(patient_text, patient_data)
            
            # Update patient data in database
            await self.firestore_service.update_patient(patient_id, patient_data)
            
            return result
            
        except Exception as e:
            print(f"Error in conversation engine: {e}")
            return {
                "response_text": "معذرت، میں آپ کی بات سمجھ نہیں سکا۔ براہ کرم دوبارہ کوشش کریں۔",
                "next_phase": "general_response",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
    
    def _initialize_patient_data(self, patient_id: str) -> Dict[str, Any]:
        """Initialize new patient data structure"""
        return {
            "patient_id": patient_id,
            "demographics": {
                "name": "",
                "age": "",
                "phone_number": ""
            },
            "problem_description": "",
            "symptoms": [],
            "medical_history": {},
            "conversation_history": [],
            "current_phase": "onboarding",
            "questions_asked": 0,
            "max_questions": 20,
            "min_questions": 10,
            "assessment_complete": False,
            "alert_level": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    async def _extract_information_intelligently(self, patient_text: str, patient_data: Dict[str, Any]):
        """Extract information using AI intelligence, not keywords"""
        
        extraction_prompt = f"""
        You are an intelligent medical assistant. Extract information from this patient response: "{patient_text}"
        
        Current patient data:
        - Demographics: {json.dumps(patient_data.get('demographics', {}), ensure_ascii=False)}
        - Problem: {patient_data.get('problem_description', '')}
        - Symptoms: {patient_data.get('symptoms', [])}
        - Medical History: {json.dumps(patient_data.get('medical_history', {}), ensure_ascii=False)}
        - Current Phase: {patient_data.get('current_phase', '')}
        
        INTELLIGENT EXTRACTION RULES:
        1. Understand the MEANING, not just keywords
        2. Extract information based on CONTEXT
        3. Capture what the patient is ACTUALLY saying
        4. Be intelligent about medical information
        
        Extract as JSON:
        {{
            "demographics": {{
                "name": "extracted name if mentioned",
                "age": "extracted age if mentioned",
                "phone_number": "extracted phone if mentioned"
            }},
            "problem_description": "main problem/concern described",
            "symptoms": ["list of symptoms mentioned"],
            "medical_history": {{
                "previous_conditions": "any previous medical conditions",
                "medications": "any medications mentioned",
                "allergies": "any allergies mentioned",
                "family_history": "any family medical history",
                "previous_pregnancies": "any pregnancy history",
                "surgeries": "any previous surgeries"
            }},
            "symptom_details": {{
                "duration": "how long symptoms present",
                "severity": "severity level mentioned",
                "frequency": "how often symptoms occur",
                "triggers": "what triggers symptoms",
                "associated_symptoms": "other symptoms mentioned"
            }}
        }}
        
        Examples:
        - "میرا نام فاطمہ ہے" → {{"demographics": {{"name": "فاطمہ"}}}}
        - "میری عمر 25 سال ہے" → {{"demographics": {{"age": "25"}}}}
        - "مجھے پیٹ میں درد ہے" → {{"problem_description": "پیٹ میں درد", "symptoms": ["پیٹ میں درد"]}}
        - "یہ ایک ہفتے سے ہو رہا ہے" → {{"symptom_details": {{"duration": "ایک ہفتہ"}}}}
        - "شدید درد ہے" → {{"symptom_details": {{"severity": "شدید"}}}}
        
        Return ONLY valid JSON. If no new information, return empty {{}}.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            try:
                if "{" in response_text and "}" in response_text:
                    start_idx = response_text.find("{")
                    end_idx = response_text.rfind("}") + 1
                    json_text = response_text[start_idx:end_idx]
                    extracted_info = json.loads(json_text)
                else:
                    extracted_info = {}
            except json.JSONDecodeError:
                extracted_info = {}
            
            # Update patient data with extracted information
            self._update_patient_data(extracted_info, patient_data)
            
        except Exception as e:
            print(f"Error in extraction: {e}")
    
    def _update_patient_data(self, extracted_info: Dict[str, Any], patient_data: Dict[str, Any]):
        """Update patient data with extracted information"""
        
        # Update demographics
        if "demographics" in extracted_info:
            for key, value in extracted_info["demographics"].items():
                if value and not patient_data["demographics"].get(key):
                    patient_data["demographics"][key] = value
        
        # Update problem description
        if "problem_description" in extracted_info and extracted_info["problem_description"]:
            if not patient_data.get("problem_description"):
                patient_data["problem_description"] = extracted_info["problem_description"]
        
        # Update symptoms
        if "symptoms" in extracted_info and extracted_info["symptoms"]:
            for symptom in extracted_info["symptoms"]:
                if symptom not in patient_data["symptoms"]:
                    patient_data["symptoms"].append(symptom)
        
        # Update medical history
        if "medical_history" in extracted_info and extracted_info["medical_history"]:
            for key, value in extracted_info["medical_history"].items():
                if value and not patient_data["medical_history"].get(key):
                    patient_data["medical_history"][key] = value
        
        # Update symptom details
        if "symptom_details" in extracted_info and extracted_info["symptom_details"]:
            if "symptom_details" not in patient_data:
                patient_data["symptom_details"] = {}
            for key, value in extracted_info["symptom_details"].items():
                if value:
                    patient_data["symptom_details"][key] = value
    
    async def _determine_next_response(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the next response based on current phase and patient data"""
        
        current_phase = patient_data.get("current_phase", "onboarding")
        
        if current_phase == "onboarding":
            return await self._handle_onboarding_phase(patient_text, patient_data)
        elif current_phase == "problem_collection":
            return await self._handle_problem_collection_phase(patient_text, patient_data)
        elif current_phase == "symptom_exploration":
            return await self._handle_symptom_exploration_phase(patient_text, patient_data)
        elif current_phase == "assessment":
            return await self._handle_assessment_phase(patient_text, patient_data)
        else:
            return await self._handle_general_response(patient_text, patient_data)
    
    async def _handle_onboarding_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle onboarding phase - collect name, age, phone"""
        
        demographics = patient_data.get("demographics", {})
        
        # Check what's missing
        missing_info = []
        if not demographics.get("name"):
            missing_info.append("نام")
        if not demographics.get("age"):
            missing_info.append("عمر")
        if not demographics.get("phone_number"):
            missing_info.append("فون نمبر")
        
        if missing_info:
            if not patient_data.get("has_greeted"):
                patient_data["has_greeted"] = True
                response_text = f"وعلیکم السلام! میں آپ کی گائناکالوجی کی مدد کرنے کے لئے ہوں۔ براہ کرم مجھے اپنا {missing_info[0]} بتائیں۔"
            else:
                response_text = f"براہ کرم مجھے اپنا {missing_info[0]} بتائیں۔"
            
            return {
                "response_text": response_text,
                "next_phase": "onboarding",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
        else:
            # Onboarding complete, move to problem collection
            patient_data["current_phase"] = "problem_collection"
            name = demographics.get("name", "صاحبہ")
            response_text = f"{name} صاحبہ، آپ کا آن بورڈنگ مکمل ہو گیا ہے۔ اب مجھے بتائیں کہ آپ کو کیا مسئلہ ہے؟"
            
            return {
                "response_text": response_text,
                "next_phase": "problem_collection",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
    
    async def _handle_problem_collection_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle problem collection phase - understand the main problem"""
        
        if not patient_data.get("problem_description"):
            # Ask for problem if not collected yet
            response_text = "براہ کرم مجھے بتائیں کہ آپ کو کیا مسئلہ ہے؟ آپ کی کیا تکلیف ہے؟"
            return {
                "response_text": response_text,
                "next_phase": "problem_collection",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
        else:
            # Problem collected, move to symptom exploration
            patient_data["current_phase"] = "symptom_exploration"
            response_text = "شکریہ۔ اب میں آپ کے مسئلے کے بارے میں مزید تفصیلات جاننا چاہتا ہوں۔"
            
            return {
                "response_text": response_text,
                "next_phase": "symptom_exploration",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
    
    async def _handle_symptom_exploration_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle symptom exploration phase - intelligent follow-up questions"""
        
        questions_asked = patient_data.get("questions_asked", 0)
        max_questions = patient_data.get("max_questions", 20)
        min_questions = patient_data.get("min_questions", 10)
        
        # Check if we have enough information for assessment
        if questions_asked >= min_questions and self._has_sufficient_information(patient_data):
            patient_data["current_phase"] = "assessment"
            return await self._handle_assessment_phase(patient_text, patient_data)
        
        # Check if we've reached maximum questions
        if questions_asked >= max_questions:
            patient_data["current_phase"] = "assessment"
            return await self._handle_assessment_phase(patient_text, patient_data)
        
        # Generate intelligent follow-up question
        question = await self._generate_intelligent_question(patient_text, patient_data)
        
        # Increment question count
        patient_data["questions_asked"] = questions_asked + 1
        
        return {
            "response_text": question,
            "next_phase": "symptom_exploration",
            "patient_data": patient_data,
            "action": "continue_conversation"
        }
    
    def _has_sufficient_information(self, patient_data: Dict[str, Any]) -> bool:
        """Check if we have sufficient information for assessment"""
        
        # Check if we have basic information
        has_problem = bool(patient_data.get("problem_description"))
        has_symptoms = len(patient_data.get("symptoms", [])) > 0
        has_medical_history = len(patient_data.get("medical_history", {})) > 0
        
        # Need at least problem description and some symptoms
        return has_problem and has_symptoms
    
    async def _generate_intelligent_question(self, patient_text: str, patient_data: Dict[str, Any]) -> str:
        """Generate intelligent follow-up questions based on patient's responses"""
        
        conversation_context = ""
        for i, msg in enumerate(patient_data["conversation_history"][-5:]):
            conversation_context += f"Turn {i+1}: {msg['patient_text']}\n"
        
        question_prompt = f"""
        You are a SENIOR PAKISTANI GYNECOLOGIST with 20+ years of experience. You are conducting an intelligent consultation.
        
        PATIENT INFORMATION:
        - Name: {patient_data.get('demographics', {}).get('name', 'Unknown')}
        - Age: {patient_data.get('demographics', {}).get('age', 'Unknown')}
        - Problem: {patient_data.get('problem_description', '')}
        - Symptoms: {patient_data.get('symptoms', [])}
        - Medical History: {json.dumps(patient_data.get('medical_history', {}), ensure_ascii=False)}
        - Questions Asked: {patient_data.get('questions_asked', 0)}/{patient_data.get('max_questions', 20)}
        
        CONVERSATION HISTORY:
        {conversation_context}
        
        CURRENT PATIENT RESPONSE: "{patient_text}"
        
        INTELLIGENT QUESTIONING APPROACH:
        1. **LISTEN CAREFULLY**: What is the patient telling you?
        2. **ANALYZE CONTEXT**: What information do you still need?
        3. **ASK RELEVANT QUESTION**: Ask ONE natural, relevant question
        
        QUESTIONING STRATEGY:
        - Ask about symptoms related to their problem
        - Ask about medical history relevant to their condition
        - Ask about duration, severity, triggers
        - Ask about associated symptoms
        - Ask about previous treatments or medications
        
        RULES:
        - Ask ONLY ONE question per turn
        - Make it natural and conversational in Urdu
        - Don't repeat questions already asked
        - Focus on information relevant to their specific problem
        - Be empathetic and professional
        - Don't give medical advice or diagnosis
        
        Generate ONE intelligent, relevant question in Urdu that a senior gynecologist would ask based on the patient's problem and their latest response.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": question_prompt}],
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating question: {e}")
            return "کیا آپ کوئی اور علامات بھی محسوس کر رہی ہیں؟"
    
    async def _handle_assessment_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle assessment phase - determine alert level and provide recommendations"""
        
        # Generate assessment using AI
        assessment = await self._generate_assessment(patient_data)
        
        # Determine alert level
        alert_level = assessment.get("alert_level", "yellow")
        patient_data["alert_level"] = alert_level
        patient_data["assessment_complete"] = True
        
        # Generate response based on alert level
        if alert_level == "red":
            response_text = f"{assessment.get('assessment_summary', '')}\n\n🚨 آپ کو فوراً اپنے ڈاکٹر کے پاس جانا چاہیے"
        elif alert_level == "yellow":
            response_text = f"{assessment.get('assessment_summary', '')}\n\n⚠️ آپ کو ڈاکٹر کو دکھا لینا چاہیے جب آپ کے پاس وقت ہو۔ یہ بہت urgent نہیں ہے"
        else:
            response_text = f"{assessment.get('assessment_summary', '')}\n\n✅ آپ کا طبی رپورٹ تیار ہو گیا ہے۔ اللہ حافظ!"
        
        return {
            "response_text": response_text,
            "next_phase": "assessment",
            "patient_data": patient_data,
            "action": "generate_emr"
        }
    
    async def _generate_assessment(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate medical assessment using AI"""
        
        assessment_prompt = f"""
        You are a SENIOR PAKISTANI GYNECOLOGIST performing a medical assessment.
        
        PATIENT INFORMATION:
        - Name: {patient_data.get('demographics', {}).get('name', 'Unknown')}
        - Age: {patient_data.get('demographics', {}).get('age', 'Unknown')}
        - Problem: {patient_data.get('problem_description', '')}
        - Symptoms: {patient_data.get('symptoms', [])}
        - Medical History: {json.dumps(patient_data.get('medical_history', {}), ensure_ascii=False)}
        - Symptom Details: {json.dumps(patient_data.get('symptom_details', {}), ensure_ascii=False)}
        
        ASSESSMENT CRITERIA:
        
        RED ALERT (Emergency - Immediate medical attention required):
        - Severe bleeding (heavy, continuous, with clots)
        - Severe pain (unbearable, affecting daily activities)
        - High fever with gynecological symptoms
        - Signs of infection (fever, severe pain, discharge)
        - Pregnancy complications (severe bleeding, severe pain)
        - Any life-threatening symptoms
        
        YELLOW ALERT (Urgent - Medical attention needed soon):
        - Moderate symptoms affecting daily life
        - Persistent symptoms not improving
        - Concerning symptoms requiring investigation
        - Routine gynecological concerns
        
        GREEN ALERT (Routine - Standard care):
        - Mild symptoms
        - Routine check-ups
        - Preventive care
        
        Return as JSON:
        {{
            "alert_level": "red" or "yellow" or "green",
            "assessment_summary": "brief assessment in Urdu",
            "clinical_impression": "likely diagnosis or condition",
            "recommendations": "what patient should do next"
        }}
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": assessment_prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            try:
                if "{" in response_text and "}" in response_text:
                    start_idx = response_text.find("{")
                    end_idx = response_text.rfind("}") + 1
                    json_text = response_text[start_idx:end_idx]
                    return json.loads(json_text)
                else:
                    return {"alert_level": "yellow", "assessment_summary": "عام طبی مشورہ"}
            except json.JSONDecodeError:
                return {"alert_level": "yellow", "assessment_summary": "عام طبی مشورہ"}
                
        except Exception as e:
            print(f"Error generating assessment: {e}")
            return {"alert_level": "yellow", "assessment_summary": "عام طبی مشورہ"}
    
    async def _handle_general_response(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general responses"""
        
        if not patient_data.get("has_greeted"):
            patient_data["has_greeted"] = True
            response_text = "وعلیکم السلام! میں آپ کی گائناکالوجی کی مدد کرنے کے لئے ہوں۔ براہ کرم مجھے اپنا نام بتائیں۔"
        else:
            response_text = "براہ کرم مجھے اپنا نام بتائیں۔"
        
        return {
            "response_text": response_text,
            "next_phase": "onboarding",
            "patient_data": patient_data,
            "action": "continue_conversation"
        }
    
    async def generate_emr(self, patient_id: str) -> bool:
        """Generate comprehensive EMR"""
        
        try:
            patient_data = await self.firestore_service.get_patient(patient_id)
            if not patient_data:
                print(f"❌ No patient data found for {patient_id}")
                return False
            
            # Ensure patient_data is a dictionary
            if not isinstance(patient_data, dict):
                print(f"❌ Patient data is not a dictionary: {type(patient_data)}")
                return False
            
            # Convert datetime objects to strings
            clean_patient_data = self._convert_datetime_to_string(patient_data)
            
            # Remove conversation history from EMR data
            emr_patient_data = clean_patient_data.copy()
            if 'conversation_history' in emr_patient_data:
                del emr_patient_data['conversation_history']
            
            # Ensure demographics exists and is a dict
            demographics = emr_patient_data.get('demographics', {})
            if not isinstance(demographics, dict):
                demographics = {}
            
            # Ensure other fields exist
            symptom_details = emr_patient_data.get('symptom_details', {})
            if not isinstance(symptom_details, dict):
                symptom_details = {}
                
            medical_history = emr_patient_data.get('medical_history', {})
            if not isinstance(medical_history, dict):
                medical_history = {}
            
            # Ensure alert level is set - if not present, generate one based on symptoms
            alert_level = emr_patient_data.get('alert_level')
            if not alert_level or alert_level not in ['red', 'yellow', 'green']:
                print(f"⚠️ No valid alert level found, generating assessment...")
                assessment = await self._generate_assessment(emr_patient_data)
                alert_level = assessment.get("alert_level", "yellow")
                emr_patient_data["alert_level"] = alert_level
                emr_patient_data["assessment_summary"] = assessment.get("assessment_summary", "Standard gynecological consultation")
                emr_patient_data["clinical_impression"] = assessment.get("clinical_impression", "Requires further evaluation")
                print(f"✅ Generated alert level: {alert_level}")
            
            emr_prompt = f"""
            Generate a comprehensive gynecological EMR (Electronic Medical Record) in English for this patient.
            
            Patient Data: {json.dumps(emr_patient_data, ensure_ascii=False)}
            
            Create a detailed professional gynecological medical report with the following EXACT structure and formatting:
            
            # ELECTRONIC MEDICAL RECORD (EMR)
            ## Gynecological Consultation Report
            
            ### 1. PATIENT DEMOGRAPHICS
            **Name:** {demographics.get('name', 'Unknown')}
            **Age:** {demographics.get('age', 'Unknown')}
            **Phone Number:** {demographics.get('phone_number', 'Unknown')}
            **Date of Consultation:** {datetime.now().strftime('%Y-%m-%d')}
            
            ### 2. PRESENTING PROBLEM
            **Chief Complaint:** {emr_patient_data.get('problem_description', 'Unknown')}
            
            ### 3. SYMPTOMS
            **Primary Symptoms:** {', '.join(emr_patient_data.get('symptoms', []))}
            
            ### 4. SYMPTOM DETAILS
            **Duration:** {symptom_details.get('duration', 'Unknown')}
            **Severity:** {symptom_details.get('severity', 'Unknown')}
            **Frequency:** {symptom_details.get('frequency', 'Unknown')}
            **Triggers:** {symptom_details.get('triggers', 'Unknown')}
            **Associated Symptoms:** {symptom_details.get('associated_symptoms', 'Unknown')}
            
            ### 5. MEDICAL HISTORY
            **Previous Conditions:** {medical_history.get('previous_conditions', 'Unknown')}
            **Current Medications:** {medical_history.get('medications', 'Unknown')}
            **Known Allergies:** {medical_history.get('allergies', 'Unknown')}
            **Family History:** {medical_history.get('family_history', 'Unknown')}
            **Previous Pregnancies:** {medical_history.get('previous_pregnancies', 'Unknown')}
            **Previous Surgeries:** {medical_history.get('surgeries', 'Unknown')}
            
            ### 6. MEDICAL ASSESSMENT
            **Alert Level:** {alert_level.upper()}
            **Assessment Summary:** {emr_patient_data.get('assessment_summary', 'Standard gynecological consultation')}
            **Clinical Impression:** {emr_patient_data.get('clinical_impression', 'Requires further evaluation')}
            
            ### 7. AI MEDICAL SUMMARY
            [Generate a comprehensive medical summary in English that consolidates all the information above. This should be a detailed clinical assessment of the patient's condition, symptoms, and medical history.]
            
            ### 8. RECOMMENDATIONS
            [Provide detailed recommendations for further care, follow-up, and treatment options. Include specific next steps, referrals, or treatments as appropriate.]
            
            ### 9. FOLLOW-UP INSTRUCTIONS
            [Provide clear follow-up instructions including when to return, what to monitor, and when to seek immediate care.]
            
            ---
            **Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            **Generated By:** AI Gynecological Assistant
            
            Format this as a professional medical report with proper markdown formatting, clear headings, and structured sections. Use bold text for field labels and maintain professional medical terminology throughout.
            """
            
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": emr_prompt}],
                temperature=0.1
            )
            
            emr_content = response.choices[0].message.content.strip()
            
            # Save EMR to Firestore
            emr_data = {
                "patient_id": patient_id,
                "emr_content": emr_content,
                "alert_level": alert_level,
                "assessment_summary": emr_patient_data.get('assessment_summary', 'Standard gynecological consultation'),
                "clinical_impression": emr_patient_data.get('clinical_impression', 'Requires further evaluation'),
                "created_at": datetime.now().isoformat(),
                "patient_data": emr_patient_data
            }
            
            # Update patient data with the alert level and assessment
            await self.firestore_service.update_patient(patient_id, {
                "alert_level": alert_level,
                "assessment_summary": emr_patient_data.get('assessment_summary', 'Standard gynecological consultation'),
                "clinical_impression": emr_patient_data.get('clinical_impression', 'Requires further evaluation'),
                "assessment_complete": True,
                "updated_at": datetime.now().isoformat()
            })
            
            await self.firestore_service.create_emr(patient_id, emr_data)
            print(f"✅ EMR generated successfully with alert level: {alert_level}")
            return True
            
        except Exception as e:
            print(f"Error generating EMR: {e}")
            return False
    
    def _convert_datetime_to_string(self, obj):
        """Convert datetime objects to strings recursively"""
        if isinstance(obj, dict):
            return {key: self._convert_datetime_to_string(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetime_to_string(item) for item in obj]
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        else:
            return obj

# Create global instance
intelligent_conversation_engine = IntelligentConversationEngine()
