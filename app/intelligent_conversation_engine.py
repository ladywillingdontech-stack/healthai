import json
import openai
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.firestore_service import FirestoreService
from app.config import settings

class IntelligentConversationEngine:
    def __init__(self):
        self.firestore_service = FirestoreService()
        # Configure OpenAI
        openai.api_key = settings.openai_api_key
        
        # Define all 60 structured questions
        self.questions = self._initialize_questions()
    
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
            
            # Get current question if in questionnaire phase
            current_phase = patient_data.get("current_phase", "onboarding")
            current_question_index = patient_data.get("current_question_index", 0)
            
            # Extract information if in questionnaire phase and patient has responded
            if current_phase == "questionnaire" and current_question_index < len(self.questions) and patient_text.strip():
                current_question = self.questions[current_question_index]
                await self._extract_information_intelligently(patient_text, patient_data, current_question)
                
                # Special handling for question 8 (children info) - extract first_pregnancy and number_of_children
                if current_question_index == 7:  # Question 8 is index 7 (0-based)
                    await self._extract_children_info(patient_text, patient_data)
                
                # Special handling for question 13 (pregnancy month) - extract month and determine trimester
                if current_question_index == 12:  # Question 13 is index 12 (0-based)
                    await self._extract_pregnancy_month(patient_text, patient_data)
                
                # Special handling for question 24 (anatomy scan) - check for twins
                if current_question_index == 23:  # Question 24 is index 23 (0-based)
                    await self._check_for_twins(patient_text, patient_data)
                
                # Special handling for question 29 (recent scan) - check for twins
                if current_question_index == 28:  # Question 29 is index 28 (0-based)
                    await self._check_for_twins(patient_text, patient_data)
                
                # Get next valid question index (skip obstetric history if first pregnancy, skip question 48 if no twins, skip 23-30 if first trimester)
                next_index = self._get_next_valid_question_index(current_question_index + 1, patient_data)
                patient_data["current_question_index"] = next_index
            
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
    
    def _initialize_questions(self) -> List[Dict[str, Any]]:
        """Initialize all structured questions"""
        return [
            # Patient Profile (1-13)
            {"id": 1, "text": "Aapka pura naam kya hai?", "field": "demographics.name", "category": "patient_profile"},
            {"id": 2, "text": "Aapka shanakhti card ka number kya hai?", "field": "demographics.id_card_number", "category": "patient_profile"},
            {"id": 3, "text": "Aap kis jamat tak parhi hain?", "field": "demographics.education", "category": "patient_profile"},
            {"id": 4, "text": "Aap kis ilaqe mein rehti hain?", "field": "demographics.area", "category": "patient_profile"},
            {"id": 5, "text": "Aap kya kaam karti hain?", "field": "demographics.occupation", "category": "patient_profile"},
            {"id": 6, "text": "Aapki umar kitni hai?", "field": "demographics.age", "category": "patient_profile"},
            {"id": 7, "text": "Shaadi ko kitna arsa ho gaya hai? Khandan mein hoyi hai ya baahir? Kya apka shohar apka cousin hai?", "field": "demographics.marriage_info", "category": "patient_profile"},
            {"id": 8, "text": "Aapne kitne bachay hain? Apka pehla huml hai?", "field": "demographics.children_info", "category": "patient_profile"},
            {"id": 9, "text": "Khudanakhasta koi huml zaya tou nahi hoa?", "field": "demographics.miscarriages", "category": "patient_profile"},
            {"id": 10, "text": "Koi bacha fout tou nahi hoa?", "field": "demographics.child_deaths", "category": "patient_profile"},
            {"id": 11, "text": "Aapko mahwari ki aakhri date kab ayi thi? Aakhri tareekh yaad hai?", "field": "demographics.last_menstrual_period", "category": "patient_profile"},
            {"id": 12, "text": "Kiya mahwari apko waqt per aati hai?", "field": "demographics.regular_periods", "category": "patient_profile"},
            {"id": 13, "text": "Aapke hisaab se huml ka konsa mahina chal raha?", "field": "current_pregnancy.pregnancy_month", "category": "patient_profile"},
            
            # Presenting Complaint (14)
            {"id": 14, "text": "Aap kis maslay k sath ayi hain? Thora tafseelan btayen mujhy?", "field": "problem_description", "category": "presenting_complaint"},
            
            # Current Pregnancy (15-22)
            {"id": 15, "text": "Huml khudi hoa tha ya phir dawai khani pari?", "field": "current_pregnancy.conception_method", "category": "current_pregnancy"},
            {"id": 16, "text": "Kiya is huml mein aapki marzi shamil thi?", "field": "current_pregnancy.intended", "category": "current_pregnancy"},
            {"id": 17, "text": "Aapko huml kese pata chala hai?", "field": "current_pregnancy.discovery_method", "category": "current_pregnancy"},
            {"id": 18, "text": "Pishaab ka test kiya tha?", "field": "current_pregnancy.urine_test", "category": "current_pregnancy"},
            {"id": 19, "text": "Shuru ke dino mein ultrasound karaya tha?", "field": "current_pregnancy.early_ultrasound", "category": "current_pregnancy"},
            {"id": 20, "text": "Aapne folic acid li huml se pehle aur shuru ke dino mein?", "field": "current_pregnancy.folic_acid", "category": "current_pregnancy"},
            {"id": 21, "text": "Aapke koi khoon pishaab ke koi test hoye? If yes, then konse hoye?", "field": "current_pregnancy.tests_info", "category": "current_pregnancy"},
            {"id": 22, "text": "Hamal ke shuru ke dino mein kiya apko in main se koi alamaat mehsoos hui hain? dard ya bukhaar ya chakkar aye hoon ya khoon para ho ya ulti ayi ho, dil kharab hoa ho?", "field": "current_pregnancy.early_symptoms", "category": "current_pregnancy"},
            
            # Second and Third Trimesters (23-30)
            {"id": 23, "text": "Apko bache ki harkat hona kab mahsoos hoyi? Theek hai bache ki harkat?", "field": "current_pregnancy.fetal_movement", "category": "second_third_trimester"},
            {"id": 24, "text": "Apka panchwain mahinay main bachay ki banwat wala ultrasound(barra ultrasound) hua tha?", "field": "current_pregnancy.anatomy_scan", "category": "second_third_trimester"},
            {"id": 25, "text": "Kiya ap nay baa-qaidgi se checkup kerwaya hai? Aur khoon pishaab ke test hoye hain? If yes, Hb kitni hai? If no, kya aapko thakawat, saans ka phoolna, ya dil ki dharkan tez hone ka masla hota hai?", "field": "current_pregnancy.checkup_info", "category": "second_third_trimester"},
            {"id": 26, "text": "Aapke sugar aur blood pressure ke test hoye thay? Koi masla tou nahi aya? If yes, aapko is masle ke liye koi dawai khaani parhti hai?", "field": "current_pregnancy.sugar_bp_info", "category": "second_third_trimester"},
            {"id": 27, "text": "Aap taqat ki dawain le rahi hain?", "field": "current_pregnancy.supplements", "category": "second_third_trimester"},
            {"id": 28, "text": "Kiya apko hamal k doran in main se koi alamaat mehsoos hui hain: nallon men dard, kachi dardain, khoon ya paani ka parna, ya bachay ki harkat men kami mehsoos hui hai?", "field": "current_pregnancy.complications", "category": "second_third_trimester"},
            {"id": 29, "text": "If in the third trimester, abhi ka koi recent scan hai apke paas? Koi masla tou nahi aya?", "field": "current_pregnancy.recent_scan", "category": "second_third_trimester"},
            {"id": 30, "text": "Pregnancy ke baare mein koi aur maloomat jo aap share karna chahti hain?", "field": "current_pregnancy.additional_info", "category": "second_third_trimester"},
            
            # Obstetric History - For one child (31-41)
            {"id": 31, "text": "Bache ki umer kiya hai?", "field": "obstetric_history.single_child.age", "category": "obstetric_history"},
            {"id": 32, "text": "Larka hai ya larki?", "field": "obstetric_history.single_child.gender", "category": "obstetric_history"},
            {"id": 33, "text": "Poore dino per paida hoa tha?", "field": "obstetric_history.single_child.full_term", "category": "obstetric_history"},
            {"id": 34, "text": "Normal hua tha? Operation se hua tha?", "field": "obstetric_history.single_child.delivery_method", "category": "obstetric_history"},
            {"id": 35, "text": "Kahan per paida hua tha? Delivery kahan pe hoyi thi?", "field": "obstetric_history.single_child.delivery_location", "category": "obstetric_history"},
            {"id": 36, "text": "If normal: Dardien khudi lagi thi ya lagwani pari thi? Kitna waqt laga bache ki padaish mein?", "field": "obstetric_history.single_child.normal_delivery_details", "category": "obstetric_history"},
            {"id": 37, "text": "If operation: Kis wajah se hua tha?", "field": "obstetric_history.single_child.operation_reason", "category": "obstetric_history"},
            {"id": 38, "text": "Padaish ke waqt bache ka wazan kitna tha?", "field": "obstetric_history.single_child.birth_weight", "category": "obstetric_history"},
            {"id": 39, "text": "Delivery ke baad koi masla tou nahi hoa? Padaish ke baad apko ya bache ko masla tou nahi hoa?", "field": "obstetric_history.single_child.post_delivery_complications", "category": "obstetric_history"},
            {"id": 40, "text": "Bacha ab theek hai? School jata hai?", "field": "obstetric_history.single_child.current_status", "category": "obstetric_history"},
            {"id": 41, "text": "Kya is huml mein sugar, blood pressure ya khoon ka masla hoa? Ya koi aur masla jo aap batana chahein?", "field": "obstetric_history.single_child.pregnancy_complications", "category": "obstetric_history"},
            
            # Obstetric History - For multiple children (42-52) - Note: This overlaps with single child questions
            # We'll handle this dynamically based on number of children
            
            # Gynecological History (42-43)
            {"id": 42, "text": "Ap khandaani mansooba bandi k liye koi tareeq istemal kerti theen is se pehlay? If yes, konsa?", "field": "gynecological_history.contraception", "category": "gynecological_history"},
            {"id": 43, "text": "Kiya ap nay kabhi bachaydaani k munh ka muaaiana(pap smear) kerwaya hain?", "field": "gynecological_history.pap_smear", "category": "gynecological_history"},
            
            # Past Medical History (44-45)
            {"id": 44, "text": "Kiya ap kisi maslay k liye koi dawayi khaa rahi hain?", "field": "past_medical_history.current_medications", "category": "past_medical_history"},
            {"id": 45, "text": "Kabhi sugar/Blood pressure/ dama/TB/Yarqan/dil ya gurdon ka masla tou nahin hua?", "field": "past_medical_history.previous_conditions", "category": "past_medical_history"},
            
            # Surgical History (46)
            {"id": 46, "text": "Apka kabhi kisi wajah se koi operation tou nae hua? Agar hua hai tou tafseelan bataiye.", "field": "surgical_history.operations", "category": "surgical_history"},
            
            # Family History (47-48)
            {"id": 47, "text": "Kiya apkay ya apkay shohar k khandan men kisi ko sugar, blood pressure, dil, TB, ya bachon men banawti naqais tou nahin hain?", "field": "family_history.medical_conditions", "category": "family_history"},
            {"id": 48, "text": "If twins then ask: Kya apkay khandaan men pehlay koi jurwan bachay hoye hain?", "field": "family_history.twins_history", "category": "family_history"},
            
            # Personal History (49-56)
            {"id": 49, "text": "Aapko kisi cheez ya koi dawai se allergy tou nahi hai? If yes: konsi allergy hai?", "field": "personal_history.allergies", "category": "personal_history"},
            {"id": 50, "text": "Aapka blood group kya hai?", "field": "personal_history.blood_group", "category": "personal_history"},
            {"id": 51, "text": "Apka wazn kitna hai?", "field": "personal_history.weight", "category": "personal_history"},
            {"id": 52, "text": "Maaf kijiye ga, kiya aap ya aap ka shohar cigarette noshi ya kisi qisam ka koi aur nasha karti hain?", "field": "personal_history.smoking_substance_use", "category": "personal_history"},
            {"id": 53, "text": "Aap ke shohar ke saath taluqaat theek hain? Apkay sath ghar per koi gali galoch/ mar peet ya zabardasti tou nahin kerta?", "field": "personal_history.relationship_status", "category": "personal_history"},
            {"id": 54, "text": "Aap ko neend theek aati hai? Agar nahi, kya wajah hai thora tafseelan batayein?", "field": "personal_history.sleep", "category": "personal_history"},
            {"id": 55, "text": "Bhook theek lagti hai? Agar nahi, kya wajah hai thora tafseelan batayein?", "field": "personal_history.appetite", "category": "personal_history"},
            {"id": 56, "text": "Apki ghiza kesi hai? Khaane mein phal, sabzian, gosht aur anday doodh ka istemaal karti hain?", "field": "personal_history.diet", "category": "personal_history"},
            
            # Socio-Economic History (57-60)
            {"id": 57, "text": "Aapke ghar mein kitne afraad hain?", "field": "socio_economic.family_size", "category": "socio_economic"},
            {"id": 58, "text": "Shohar kiya kaam kerta hai? Guzara theek se ho jata hai?", "field": "socio_economic.husband_occupation", "category": "socio_economic"},
            {"id": 59, "text": "Ap susral k sath rehti hain ya alag rehti hain?", "field": "socio_economic.living_arrangement", "category": "socio_economic"},
            {"id": 60, "text": "Iske ilawa aap kuch batana chahein gi? Aapke nazdeek zaroori ho?", "field": "additional_info", "category": "socio_economic"}
        ]
    
    def _initialize_patient_data(self, patient_id: str) -> Dict[str, Any]:
        """Initialize new patient data structure with all structured fields"""
        return {
            "patient_id": patient_id,
            "demographics": {
                "name": "",
                "id_card_number": "",
                "education": "",
                "area": "",
                "occupation": "",
                "age": "",
                "phone_number": "",
                "marriage_info": "",
                "marriage_duration": "",
                "consanguineous_marriage": False,
                "husband_cousin": False,
                "children_info": "",
                "number_of_children": 0,
                "first_pregnancy": False,
                "miscarriages": "",
                "child_deaths": "",
                "last_menstrual_period": "",
                "last_menstrual_period_remembered": False,
                "regular_periods": False
            },
            "problem_description": "",
            "current_pregnancy": {
                "pregnancy_month": "",
                "conception_method": "",
                "intended": False,
                "discovery_method": "",
                "urine_test": False,
                "early_ultrasound": False,
                "folic_acid": False,
                "tests_info": "",
                "test_types": "",
                "early_symptoms": "",
                "fetal_movement": "",
                "anatomy_scan": False,
                "checkup_info": "",
                "hb_level": "",
                "sugar_bp_info": "",
                "supplements": False,
                "complications": "",
                "recent_scan": "",
                "additional_info": ""
            },
            "obstetric_history": {
                "single_child": {},
                "multiple_children": {}
            },
            "gynecological_history": {
                "contraception": "",
                "pap_smear": False
            },
            "past_medical_history": {
                "current_medications": "",
                "previous_conditions": ""
            },
            "surgical_history": {
                "operations": ""
            },
            "family_history": {
                "medical_conditions": "",
                "twins_history": ""
            },
            "personal_history": {
                "allergies": "",
                "blood_group": "",
                "weight": "",
                "smoking_substance_use": "",
                "relationship_status": "",
                "sleep": "",
                "appetite": "",
                "diet": ""
            },
            "socio_economic": {
                "family_size": "",
                "husband_occupation": "",
                "living_arrangement": ""
            },
            "additional_info": "",
            "conversation_history": [],
            "current_phase": "onboarding",
            "current_question_index": 0,
            "assessment_complete": False,
            "alert_level": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    async def _extract_information_intelligently(self, patient_text: str, patient_data: Dict[str, Any], current_question: Dict[str, Any]):
        """Extract information from patient response and save to structured field"""
        
        field_path = current_question.get("field", "")
        question_text = current_question.get("text", "")
        
        extraction_prompt = f"""
        You are a medical assistant extracting structured information from patient responses.
        
        CURRENT QUESTION: "{question_text}"
        PATIENT RESPONSE: "{patient_text}"
        FIELD TO EXTRACT: "{field_path}"
        
        Extract the answer from the patient's response and format it appropriately based on the field type:
        
        - For text fields: Return the extracted text directly
        - For boolean fields: Return true/false
        - For numeric fields: Return the number
        - For date fields: Return the date in ISO format if possible
        
        IMPORTANT: Extract ONLY the information relevant to this specific question. Don't extract other information.
        
        Return as JSON:
        {{
            "value": "extracted value here",
            "confidence": "high/medium/low"
        }}
        
        Examples:
        - Question: "Aapki umar kitni hai?" Response: "Meri umar 25 saal hai" → {{"value": "25", "confidence": "high"}}
        - Question: "Pishaab ka test kiya tha?" Response: "Haan, kiya tha" → {{"value": true, "confidence": "high"}}
        - Question: "Aapka pura naam kya hai?" Response: "Mera naam Fatima hai" → {{"value": "Fatima", "confidence": "high"}}
        
        Return ONLY valid JSON.
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
                    extracted_value = extracted_info.get("value", patient_text)
                else:
                    extracted_value = patient_text
            except json.JSONDecodeError:
                extracted_value = patient_text
            
            # Save to structured field
            self._save_to_field(patient_data, field_path, extracted_value)
            print(f"✅ Saved answer to {field_path}: {extracted_value}")
            
        except Exception as e:
            print(f"Error in extraction: {e}")
            # Fallback: save raw response
            self._save_to_field(patient_data, field_path, patient_text)
    
    def _save_to_field(self, patient_data: Dict[str, Any], field_path: str, value: Any):
        """Save value to nested field path like 'demographics.name' or 'current_pregnancy.urine_test'"""
        parts = field_path.split(".")
        
        if len(parts) == 1:
            # Top-level field
            patient_data[field_path] = value
        else:
            # Nested field
            current = patient_data
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the final value
            current[parts[-1]] = value
    
    async def _determine_next_response(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the next response based on current phase and patient data"""
        
        current_phase = patient_data.get("current_phase", "onboarding")
        
        if current_phase == "onboarding":
            return await self._handle_onboarding_phase(patient_text, patient_data)
        elif current_phase == "problem_collection":
            return await self._handle_problem_collection_phase(patient_text, patient_data)
        elif current_phase == "questionnaire":
            return await self._handle_questionnaire_phase(patient_text, patient_data)
        elif current_phase == "assessment":
            return await self._handle_assessment_phase(patient_text, patient_data)
        elif current_phase == "completed":
            return await self._handle_completed_phase(patient_text, patient_data)
        else:
            return await self._handle_general_response(patient_text, patient_data)
    
    async def _handle_onboarding_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle onboarding phase - collect name, age, phone using AI extraction"""
        
        demographics = patient_data.get("demographics", {})
        
        # Extract information from response
        extraction_prompt = f"""
        Extract basic demographics from this response: "{patient_text}"
        
        Extract:
        - Name (if mentioned)
        - Age (if mentioned)
        - Phone number (if mentioned)
        
        Return JSON: {{"name": "", "age": "", "phone_number": ""}}
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            if "{" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                extracted = json.loads(response_text[start_idx:end_idx])
                
                if extracted.get("name") and not demographics.get("name"):
                    demographics["name"] = extracted["name"]
                if extracted.get("age") and not demographics.get("age"):
                    demographics["age"] = extracted["age"]
                if extracted.get("phone_number") and not demographics.get("phone_number"):
                    demographics["phone_number"] = extracted["phone_number"]
        except:
            pass
        
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
        """Handle problem collection phase - collect presenting complaint"""
        
        if not patient_data.get("problem_description"):
            # Extract problem from response
            if patient_text.strip():
                patient_data["problem_description"] = patient_text.strip()
                print(f"✅ Saved problem description: {patient_data['problem_description']}")
            
            # Check if we have problem now
            if patient_data.get("problem_description"):
                # Problem collected, move to questionnaire and ask first question
                patient_data["current_phase"] = "questionnaire"
                patient_data["current_question_index"] = 0
                
                # Get first question
                if len(self.questions) > 0:
                    first_question = self.questions[0]["text"]
                    response_text = f"شکریہ۔ اب میں آپ سے کچھ ضروری سوالات پوچھوں گا۔\n\n{first_question}"
                else:
                    response_text = "شکریہ۔ اب میں آپ سے کچھ ضروری سوالات پوچھوں گا۔"
                
                return {
                    "response_text": response_text,
                    "next_phase": "questionnaire",
                    "patient_data": patient_data,
                    "action": "continue_conversation"
                }
            else:
                # Ask for problem if not collected yet
                response_text = "براہ کرم مجھے بتائیں کہ آپ کو کیا مسئلہ ہے؟ آپ کی کیا تکلیف ہے؟"
                return {
                    "response_text": response_text,
                    "next_phase": "problem_collection",
                    "patient_data": patient_data,
                    "action": "continue_conversation"
                }
        else:
            # Problem already collected, move to questionnaire
            patient_data["current_phase"] = "questionnaire"
            patient_data["current_question_index"] = 0
            # Ensure starting index is valid (skip obstetric history if first pregnancy)
            patient_data["current_question_index"] = self._get_next_valid_question_index(0, patient_data)
            return await self._handle_questionnaire_phase(patient_text, patient_data)
    
    async def _extract_pregnancy_month(self, patient_text: str, patient_data: Dict[str, Any]):
        """Extract pregnancy month from question 13 response and determine trimester"""
        
        extraction_prompt = f"""
        Extract pregnancy month from this response: "{patient_text}"
        
        Extract the number of months (mahina) mentioned. The response might say:
        - "doosra mahina" = 2 months
        - "teesra mahina" = 3 months
        - "chautha mahina" = 4 months
        - "2 mahina" = 2 months
        - "3 months" = 3 months
        - Numbers written in Urdu or English
        
        Return JSON:
        {{
            "pregnancy_month": 1 or 2 or 3 or 4 or 5 or 6 or 7 or 8 or 9
        }}
        
        If multiple months mentioned or unclear, use the highest/latest month mentioned.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            if "{" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                extracted = json.loads(response_text[start_idx:end_idx])
                
                pregnancy_month = extracted.get("pregnancy_month", 0)
                
                # Store pregnancy month
                current_pregnancy = patient_data.get("current_pregnancy", {})
                current_pregnancy["pregnancy_month"] = pregnancy_month
                
                # Determine trimester
                if 1 <= pregnancy_month <= 3:
                    trimester = "first"
                elif 4 <= pregnancy_month <= 6:
                    trimester = "second"
                elif 7 <= pregnancy_month <= 9:
                    trimester = "third"
                else:
                    trimester = "unknown"
                
                current_pregnancy["trimester"] = trimester
                
                print(f"✅ Extracted pregnancy month: {pregnancy_month}, trimester: {trimester}")
        except Exception as e:
            print(f"Error extracting pregnancy month: {e}")
    
    async def _extract_children_info(self, patient_text: str, patient_data: Dict[str, Any]):
        """Extract first_pregnancy, number_of_children, and check for twins from question 8 response"""
        
        extraction_prompt = f"""
        Extract information from this response: "{patient_text}"
        
        Extract:
        1. Number of children (0, 1, 2, etc.) - extract as integer
        2. Is this first pregnancy? (true/false) - look for words like "pehla", "first", "pehli baar", "nahi", "no"
        3. Has twins? (true/false) - look for words like "jurwan", "twins", "do bache ek sath", "dual pregnancy"
        
        Return JSON:
        {{
            "number_of_children": 0 or 1 or 2 or etc.,
            "first_pregnancy": true or false,
            "has_twins": true or false
        }}
        
        Examples:
        - "Mere koi bache nahi hain, ye pehla huml hai" → {{"number_of_children": 0, "first_pregnancy": true, "has_twins": false}}
        - "Mere ek bacha hai" → {{"number_of_children": 1, "first_pregnancy": false, "has_twins": false}}
        - "Pehla huml hai, koi bacha nahi" → {{"number_of_children": 0, "first_pregnancy": true, "has_twins": false}}
        - "Do bache hain, jurwan the" → {{"number_of_children": 2, "first_pregnancy": false, "has_twins": true}}
        - "Jurwan bache hain is huml mein" → {{"number_of_children": 0, "first_pregnancy": true, "has_twins": true}}
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            if "{" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                extracted = json.loads(response_text[start_idx:end_idx])
                
                demographics = patient_data.get("demographics", {})
                demographics["number_of_children"] = extracted.get("number_of_children", 0)
                demographics["first_pregnancy"] = extracted.get("first_pregnancy", False)
                
                # Store twins info if detected
                has_twins = extracted.get("has_twins", False)
                if has_twins:
                    current_pregnancy = patient_data.get("current_pregnancy", {})
                    current_pregnancy["has_twins"] = True
                
                print(f"✅ Extracted children info: {extracted.get('number_of_children')} children, first_pregnancy: {extracted.get('first_pregnancy')}, has_twins: {has_twins}")
        except Exception as e:
            print(f"Error extracting children info: {e}")
    
    async def _check_for_twins(self, patient_text: str, patient_data: Dict[str, Any]):
        """Check if patient has twins from ultrasound/scan responses"""
        
        extraction_prompt = f"""
        Analyze this response about ultrasound/scan: "{patient_text}"
        
        Determine if the patient has TWINS (two babies) mentioned in this response.
        
        Look for:
        - Words like "jurwan", "twins", "do bache", "2 bache", "dual", "multiple"
        - Any mention of two babies, two fetuses, etc.
        
        Return JSON:
        {{
            "has_twins": true or false
        }}
        
        Examples:
        - "jurwan bache hain" → {{"has_twins": true}}
        - "do bache hain scan mein" → {{"has_twins": true}}
        - "ek bacha hai" → {{"has_twins": false}}
        - "normal hai" → {{"has_twins": false}}
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            if "{" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                extracted = json.loads(response_text[start_idx:end_idx])
                
                has_twins = extracted.get("has_twins", False)
                
                # Store twins information
                current_pregnancy = patient_data.get("current_pregnancy", {})
                current_pregnancy["has_twins"] = has_twins
                
                # Also check if they mentioned multiple children in question 8
                demographics = patient_data.get("demographics", {})
                number_of_children = demographics.get("number_of_children", 0)
                
                # If they have 2+ children and it's not explicitly stated as twins, 
                # we could infer it, but for safety, only mark as twins if explicitly mentioned
                if has_twins:
                    print(f"✅ Detected twins from scan response")
        except Exception as e:
            print(f"Error checking for twins: {e}")
    
    def _has_twins(self, patient_data: Dict[str, Any]) -> bool:
        """Check if patient has twins (current pregnancy or previous)"""
        
        # Check current pregnancy
        current_pregnancy = patient_data.get("current_pregnancy", {})
        if current_pregnancy.get("has_twins", False):
            return True
        
        # Check if number of children suggests twins (2+ children could be from twin births)
        # But we should be conservative - only if explicitly mentioned
        demographics = patient_data.get("demographics", {})
        number_of_children = demographics.get("number_of_children", 0)
        
        # If they have 2 children and mentioned "jurwan" or similar in responses, likely twins
        # For now, we'll rely on explicit detection from ultrasound responses
        
        return False
    
    def _get_pregnancy_trimester(self, patient_data: Dict[str, Any]) -> str:
        """Get current pregnancy trimester"""
        current_pregnancy = patient_data.get("current_pregnancy", {})
        trimester = current_pregnancy.get("trimester", "unknown")
        pregnancy_month = current_pregnancy.get("pregnancy_month", 0)
        
        # If trimester not set but month is available, calculate it
        if trimester == "unknown" and pregnancy_month > 0:
            if 1 <= pregnancy_month <= 3:
                return "first"
            elif 4 <= pregnancy_month <= 6:
                return "second"
            elif 7 <= pregnancy_month <= 9:
                return "third"
        
        return trimester
    
    def _get_next_valid_question_index(self, start_index: int, patient_data: Dict[str, Any]) -> int:
        """Get the next valid question index, skipping obstetric history if first pregnancy, skipping question 48 if no twins, skipping 23-30 if first trimester"""
        
        demographics = patient_data.get("demographics", {})
        number_of_children = demographics.get("number_of_children", 0)
        first_pregnancy = demographics.get("first_pregnancy", False)
        
        # If first pregnancy OR no children, skip obstetric history questions (31-41, which are indices 30-40)
        skip_obstetric_history = first_pregnancy or number_of_children == 0
        
        # Check if patient has twins
        has_twins = self._has_twins(patient_data)
        
        # Check trimester - skip questions 23-30 (second/third trimester questions) if in first trimester
        trimester = self._get_pregnancy_trimester(patient_data)
        skip_second_third_trimester = trimester == "first"  # Skip if in first trimester (months 1-3)
        
        for i in range(start_index, len(self.questions)):
            question = self.questions[i]
            question_id = question.get("id", 0)
            
            # Skip questions 31-41 (obstetric history for single child) if applicable
            if skip_obstetric_history and 31 <= question_id <= 41:
                continue
            
            # Skip questions 23-30 (second/third trimester questions) if in first trimester
            if skip_second_third_trimester and 23 <= question_id <= 30:
                continue
            
            # Skip question 48 (twins history) if patient doesn't have twins
            if question_id == 48 and not has_twins:
                continue
            
            return i
        
        # If no more valid questions, return the length (meaning we're done)
        return len(self.questions)
    
    async def _handle_questionnaire_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle questionnaire phase - ask all 60 questions sequentially, skipping irrelevant ones"""
        
        # Note: Extraction and index increment already happened in process_patient_response
        current_question_index = patient_data.get("current_question_index", 0)
        
        # Ensure we have a valid question index (skip obstetric history if needed)
        current_question_index = self._get_next_valid_question_index(current_question_index, patient_data)
        patient_data["current_question_index"] = current_question_index
        
        # Check if we've completed all questions
        if current_question_index >= len(self.questions):
            # All questions answered, move to assessment
            patient_data["current_phase"] = "assessment"
            response_text = "شکریہ! تمام سوالات مکمل ہو گئے ہیں۔ اب میں آپ کا طبی جائزہ تیار کر رہا ہوں۔"
            
            return {
                "response_text": response_text,
                "next_phase": "assessment",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
        
        # Ask the next question
        current_question = self.questions[current_question_index]
        question_text = current_question["text"]
        
        response_text = question_text
        
        return {
            "response_text": response_text,
            "next_phase": "questionnaire",
            "patient_data": patient_data,
            "action": "continue_conversation"
        }
    
    async def _handle_assessment_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle assessment phase - determine alert level and provide recommendations"""
        
        # Check if assessment is already complete
        if patient_data.get("assessment_complete", False):
            # Assessment is already complete, skip to next phase
            patient_data["current_phase"] = "completed"
            return await self._handle_completed_phase(patient_text, patient_data)
        
        # Generate assessment using AI
        assessment = await self._generate_assessment(patient_data)
        
        # Determine alert level
        alert_level = assessment.get("alert_level", "yellow")
        patient_data["alert_level"] = alert_level
        patient_data["assessment_complete"] = True
        patient_data["current_phase"] = "completed"
        
        # Store assessment details in patient_data
        patient_data["assessment_summary"] = assessment.get('assessment_summary', '')
        patient_data["clinical_impression"] = assessment.get('clinical_impression', '')
        
        # Generate response based on alert level
        if alert_level == "red":
            response_text = f"{assessment.get('assessment_summary', '')}\n\n🚨 آپ کو فوراً اپنے ڈاکٹر کے پاس جانا چاہیے"
        elif alert_level == "yellow":
            response_text = f"{assessment.get('assessment_summary', '')}\n\n⚠️ آپ کو ڈاکٹر کو دکھا لینا چاہیے جب آپ کے پاس وقت ہو۔ یہ بہت urgent نہیں ہے"
        else:
            response_text = f"{assessment.get('assessment_summary', '')}\n\n✅ آپ کا طبی رپورٹ تیار ہو گیا ہے۔ اللہ حافظ!"
        
        return {
            "response_text": response_text,
            "next_phase": "completed",
            "patient_data": patient_data,
            "action": "generate_emr"
        }
    
    async def _generate_assessment(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate medical assessment using AI based on all collected structured data"""
        
        assessment_prompt = f"""
        You are a SENIOR PAKISTANI GYNECOLOGIST performing a comprehensive medical assessment.
        
        COMPLETE PATIENT INFORMATION:
        {json.dumps(patient_data, ensure_ascii=False, indent=2)}
        
        ASSESSMENT CRITERIA:
        
        RED ALERT (Emergency - Immediate medical attention required):
        - Severe bleeding (heavy, continuous, with clots)
        - Severe pain (unbearable, affecting daily activities)
        - High fever with gynecological symptoms
        - Signs of infection (fever, severe pain, discharge)
        - Pregnancy complications (severe bleeding, severe pain, complications)
        - Any life-threatening symptoms
        - Critical pregnancy issues
        
        YELLOW ALERT (Urgent - Medical attention needed soon):
        - Moderate symptoms affecting daily life
        - Persistent symptoms not improving
        - Concerning symptoms requiring investigation
        - Routine gynecological concerns
        - Pregnancy concerns requiring follow-up
        
        GREEN ALERT (Routine - Standard care):
        - Mild symptoms
        - Routine check-ups
        - Preventive care
        - Normal pregnancy progression
        
        Analyze ALL the collected information including:
        - Presenting complaint
        - Current pregnancy status and complications
        - Obstetric history
        - Past medical history
        - Family history
        - Personal history
        
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
    
    async def _handle_completed_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completed phase - conversation is done"""
        
        response_text = "✅ آپ کا طبی رپورٹ تیار ہو گیا ہے۔ اللہ حافظ!"
        
        return {
            "response_text": response_text,
            "next_phase": "completed",
            "patient_data": patient_data,
            "action": "end_conversation"
        }
    
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
            
            Complete Patient Data: {json.dumps(emr_patient_data, ensure_ascii=False, indent=2)}
            
            Create a detailed professional gynecological medical report using ALL the structured information collected from the 60-question questionnaire. Include the following sections:
            
            # ELECTRONIC MEDICAL RECORD (EMR)
            ## Gynecological Consultation Report
            
            ### 1. PATIENT DEMOGRAPHICS
            Include: Name, Age, ID Card Number, Education Level, Area, Occupation, Phone Number, Marriage Information, Children Information, Menstrual History
            
            ### 2. PRESENTING COMPLAINT
            Chief Complaint: {emr_patient_data.get('problem_description', 'Not specified')}
            
            ### 3. CURRENT PREGNANCY (if applicable)
            Include all details: Pregnancy month, Conception method, Intended/Unintended, Discovery method, Tests done, Early symptoms, Fetal movement, Scans, Complications, Supplements, etc.
            
            ### 4. OBSTETRIC HISTORY
            Include complete obstetric history: Previous deliveries, Birth weights, Delivery methods, Complications, etc.
            
            ### 5. GYNECOLOGICAL HISTORY
            Contraception history, Pap smear status
            
            ### 6. PAST MEDICAL HISTORY
            Current medications, Previous conditions (diabetes, hypertension, etc.)
            
            ### 7. SURGICAL HISTORY
            Previous operations and procedures
            
            ### 8. FAMILY HISTORY
            Medical conditions in family, Twins history
            
            ### 9. PERSONAL HISTORY
            Allergies, Blood group, Weight, Smoking/Substance use, Relationship status, Sleep, Appetite, Diet
            
            ### 10. SOCIO-ECONOMIC HISTORY
            Family size, Husband occupation, Living arrangement
            
            ### 11. ADDITIONAL INFORMATION
            Any other relevant information provided by patient
            
            ### 12. MEDICAL ASSESSMENT
            **Alert Level:** {alert_level.upper()}
            **Assessment Summary:** {emr_patient_data.get('assessment_summary', 'Standard gynecological consultation')}
            **Clinical Impression:** {emr_patient_data.get('clinical_impression', 'Requires further evaluation')}
            
            ### 13. COMPREHENSIVE MEDICAL SUMMARY
            Generate a detailed clinical assessment that synthesizes ALL the collected information. Provide a thorough analysis of the patient's condition based on all 60 questions answered.
            
            ### 14. RECOMMENDATIONS
            Provide detailed recommendations for further care, follow-up, investigations, and treatment options based on the complete assessment.
            
            ### 15. FOLLOW-UP INSTRUCTIONS
            Clear follow-up instructions including when to return, what to monitor, and when to seek immediate care.
            
            ---
            **Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            **Generated By:** AI Gynecological Assistant
            
            IMPORTANT: Use ALL the structured data collected. Don't leave out any important information. Format this as a professional medical report with proper markdown formatting, clear headings, and structured sections. Use bold text for field labels and maintain professional medical terminology throughout.
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
