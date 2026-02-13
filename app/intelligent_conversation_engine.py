import json
import re
import openai
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
try:
    from dateutil import parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    print("⚠️ python-dateutil not available, using manual date parsing")
from app.firestore_service import FirestoreService
from app.config import settings

class IntelligentConversationEngine:
    def __init__(self):
        self.firestore_service = FirestoreService()
        # Configure OpenAI
        openai.api_key = settings.openai_api_key
        
        # Rate limiting semaphore for OpenAI API calls to prevent overwhelming the API
        # Increased to 30 to handle more concurrent conversations
        self.openai_semaphore = asyncio.Semaphore(30)
        
        # Define all 60 structured questions
        self.questions = self._initialize_questions()
    
    async def _call_openai_async(self, model: str, messages: List[Dict], temperature: float = 0.1, max_tokens: Optional[int] = None, timeout: float = 30.0, max_retries: int = 3):
        """Make OpenAI API call asynchronously with timeout, rate limiting, and retry logic"""
        async with self.openai_semaphore:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    # Run OpenAI call in executor to avoid blocking the event loop
                    loop = asyncio.get_event_loop()
                    
                    # Create a callable for the OpenAI API
                    def _openai_call():
                        kwargs = {
                            "model": model,
                            "messages": messages,
                            "temperature": temperature
                        }
                        if max_tokens:
                            kwargs["max_tokens"] = max_tokens
                        return openai.chat.completions.create(**kwargs)
                    
                    # Run with timeout
                    response = await asyncio.wait_for(
                        loop.run_in_executor(None, _openai_call),
                        timeout=timeout
                    )
                    return response
                    
                except asyncio.TimeoutError:
                    last_exception = Exception(f"OpenAI API call timed out after {timeout}s (attempt {attempt + 1}/{max_retries})")
                    print(f"⚠️ {last_exception}")
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait 1s, 2s, 4s
                        wait_time = 2 ** attempt
                        print(f"⏳ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise last_exception
                        
                except Exception as e:
                    last_exception = e
                    error_msg = str(e)
                    print(f"⚠️ OpenAI API call error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    
                    # Don't retry on certain errors (authentication, invalid request, etc.)
                    if any(keyword in error_msg.lower() for keyword in ["authentication", "invalid", "unauthorized", "forbidden", "not found"]):
                        print(f"❌ Non-retryable error, stopping")
                        raise
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait 1s, 2s, 4s
                        wait_time = 2 ** attempt
                        print(f"⏳ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ All retry attempts failed")
                        raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise Exception("OpenAI API call failed for unknown reason")
    
    async def process_patient_response(self, patient_text: str, patient_id: str) -> Dict[str, Any]:
        """Main method to process patient responses intelligently"""
        
        try:
            # Get or create patient data
            patient_data = await self.firestore_service.get_patient(patient_id)
            if not patient_data:
                patient_data = self._initialize_patient_data(patient_id)
                await self.firestore_service.create_patient(patient_data)
            
            # Check if patient is returning after a completed visit
            current_phase = patient_data.get("current_phase", "onboarding")
            if current_phase == "completed":
                # Patient is returning - start a new visit
                await self._start_new_visit(patient_data)
                current_phase = patient_data.get("current_phase", "onboarding")
            
            # Add current response to conversation history
            patient_data["conversation_history"].append({
                "patient_text": patient_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Get current question if in questionnaire phase
            current_question_index = patient_data.get("current_question_index", 0)
            
            # Ensure current_question_index is an integer (Firestore may store as string)
            try:
                if isinstance(current_question_index, str):
                    current_question_index = int(current_question_index) if current_question_index.isdigit() else 0
                elif current_question_index is None:
                    current_question_index = 0
                else:
                    current_question_index = int(current_question_index)
            except (ValueError, TypeError):
                current_question_index = 0
            
            # Extract information if in demographics or questionnaire phase and patient has responded
            if current_phase in ["demographics", "questionnaire"] and current_question_index < len(self.questions) and patient_text.strip():
                current_question = self.questions[current_question_index]
                await self._extract_information_intelligently(patient_text, patient_data, current_question)
                
                # Special handling for question 5 (pregnancy number) - extract pregnancy number and determine if first pregnancy
                if current_question_index == 1:  # Question 5 is index 1 (0-based, after removing questions 1, 2, and 3)
                    await self._extract_pregnancy_number(patient_text, patient_data)
                
                # Special handling for question 6 (miscarriages/deaths) - only asked if 2nd+ pregnancy
                # This is handled by _get_next_valid_question_index condition
                
                # Special handling for question 7 (LMP) - check if date was remembered
                if current_question_index == 3:  # Question 7 is index 3 (0-based, after removing questions 1, 2, and 3)
                    await self._extract_lmp_info(patient_text, patient_data)
                
                # Special handling for question 9 (pregnancy month) - extract month and determine trimester
                if current_question_index == 5:  # Question 9 is index 5 (0-based, after removing questions 1, 2, and 3)
                    await self._extract_pregnancy_month(patient_text, patient_data)
                
                # Special handling for question 16 (anatomy scan) - check for twins
                current_question_id = current_question.get("id", 0)
                if current_question_id == 16:  # Question 16 (anatomy scan)
                    await self._check_for_twins(patient_text, patient_data)
                
                # Special handling for question 24 (recent scan) - check for twins and handle follow-up
                if current_question_id == 24:  # Question 24 (recent scan)
                    await self._check_for_twins(patient_text, patient_data)
                    # Check if patient said yes to having a recent scan - if yes, ask follow-up
                    await self._handle_recent_scan_followup(patient_text, patient_data)
                    
                    # If follow-up is needed, don't increment question index yet
                    current_pregnancy = patient_data.get("current_pregnancy", {})
                    if current_pregnancy.get("recent_scan_followup_needed", False):
                        # Keep current index, will ask follow-up in questionnaire phase
                        patient_data["current_question_index"] = current_question_index
                    else:
                        # No follow-up needed, move to next question
                        next_index = self._get_next_valid_question_index(current_question_index + 1, patient_data)
                        patient_data["current_question_index"] = next_index
                else:
                    # Always move to next question after extraction
                    next_index = self._get_next_valid_question_index(current_question_index + 1, patient_data)
                    patient_data["current_question_index"] = next_index
            
            # Determine next phase and response
            result = await self._determine_next_response(patient_text, patient_data)
            
            # Update patient data in database
            await self.firestore_service.update_patient(patient_id, patient_data)
            
            return result
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ Error in conversation engine: {e}")
            print(f"❌ Full traceback:\n{error_trace}")
            
            # Ensure patient_data exists for return
            if 'patient_data' not in locals() or patient_data is None:
                try:
                    patient_data = await self.firestore_service.get_patient(patient_id)
                    if not patient_data:
                        patient_data = self._initialize_patient_data(patient_id)
                except:
                    patient_data = self._initialize_patient_data(patient_id)
            
            # Instead of showing error, continue with conversation flow
            current_phase = patient_data.get("current_phase", "onboarding")
            
            # If in questionnaire phase, try to continue with next question
            if current_phase == "questionnaire":
                current_question_index = patient_data.get("current_question_index", 0)
                try:
                    if isinstance(current_question_index, str):
                        current_question_index = int(current_question_index) if current_question_index.isdigit() else 0
                    else:
                        current_question_index = int(current_question_index)
                except (ValueError, TypeError):
                    current_question_index = 0
                
                # Move to next question to avoid getting stuck
                if current_question_index < len(self.questions):
                    next_index = self._get_next_valid_question_index(current_question_index + 1, patient_data)
                    patient_data["current_question_index"] = next_index
                    
                    if next_index < len(self.questions):
                        current_question = self.questions[next_index]
                        response_text = current_question["text"]
                    else:
                        # All questions done, move to assessment
                        patient_data["current_phase"] = "assessment"
                        response_text = "شکریہ! تمام سوالات مکمل ہو گئے ہیں۔ اب میں آپ کا طبی جائزہ تیار کر رہی ہوں۔"
                        current_phase = "assessment"
                else:
                    # Already at end, move to assessment
                    patient_data["current_phase"] = "assessment"
                    response_text = "شکریہ! تمام سوالات مکمل ہو گئے ہیں۔ اب میں آپ کا طبی جائزہ تیار کر رہی ہوں۔"
                    current_phase = "assessment"
            else:
                # For other phases, just continue normally
                result = await self._determine_next_response("", patient_data)
                return result
            
            # Update patient data
            await self.firestore_service.update_patient(patient_id, patient_data)
            
            return {
                "response_text": response_text,
                "next_phase": current_phase,
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
    
    def _initialize_questions(self) -> List[Dict[str, Any]]:
        """Initialize all structured questions based on updated document"""
        return [
            # Patient Profile (Questions 1-8 from document)
            # Note: Question 1 (name) and Question 3 (age) are collected during onboarding, so not included here
            {"id": 4, "text": "Shaadi ko kitna arsa ho gaya hai? Khandaan mein hoyi hai ya baahir?", "field": "demographics.marriage_info", "category": "patient_profile"},
            {"id": 5, "text": "Apka kitnwa hamal hai? Kya is hamal mein jurwan bachy hain?", "field": "demographics.pregnancy_number", "category": "patient_profile"},
            {"id": 6, "text": "Koi hamal zaya tu nhi hua ya koi bacha fout tu nahi hua?", "field": "demographics.miscarriages_deaths", "category": "patient_profile", "condition": "if_2nd_or_more_pregnancy"},
            {"id": 7, "text": "Aapko mahwari kab ayi thi?", "field": "demographics.last_menstrual_period", "category": "patient_profile"},
            {"id": 8, "text": "Kiya mahwari apko waqt per aati hai?", "field": "demographics.regular_periods", "category": "patient_profile", "condition": "if_lmp_not_remembered"},
            {"id": 9, "text": "Aapke hisaab se huml ka konsa mahina chal raha?", "field": "current_pregnancy.pregnancy_month", "category": "patient_profile"},
            
            # Presenting Complaint - Main question (handled in problem_collection phase)
            # Follow-up questions are dynamic based on complaint type
            
            # Current Pregnancy - First Trimester (4 questions)
            {"id": 10, "text": "Hamal khudi hua tha ya dawai khani pari?", "field": "current_pregnancy.conception_method", "category": "first_trimester"},
            {"id": 11, "text": "Aapko hamal ka kesay pata chala?", "field": "current_pregnancy.discovery_method", "category": "first_trimester"},
            {"id": 12, "text": "Shuru ke dino mein ultrasound karaya tha?", "field": "current_pregnancy.early_ultrasound", "category": "first_trimester"},
            {"id": 13, "text": "Aapne hamal se pehle aur shuru ke dino mein foliic acid li h?", "field": "current_pregnancy.folic_acid", "category": "first_trimester"},
            {"id": 14, "text": "Kia apko shoro k dino men ulti, bukhar ya khoon prnay ki shikayat hui ho?", "field": "current_pregnancy.early_symptoms", "category": "first_trimester"},
            
            # Current Pregnancy - Second and Third Trimesters (8 questions)
            {"id": 15, "text": "Apko bache ki harkat hona kab mahsoos hui aur theek ho ri h?", "field": "current_pregnancy.fetal_movement", "category": "second_third_trimester"},
            {"id": 16, "text": "Apka panchwain mahinay main bachay ki banawat wala ultrasound hua tha?", "field": "current_pregnancy.anatomy_scan", "category": "second_third_trimester"},
            {"id": 17, "text": "Kiya ap baa-qaidgi se checkup kerwati hain?", "field": "current_pregnancy.regular_checkup", "category": "second_third_trimester"},
            {"id": 18, "text": "khoon pishaap ke test hoye hain?", "field": "current_pregnancy.blood_urine_tests", "category": "second_third_trimester"},
            {"id": 19, "text": "Hb kitni hai?", "field": "current_pregnancy.hb_level_symptoms", "category": "second_third_trimester", "condition": "if_blood_test_answered"},
            {"id": 20, "text": "Aapke sugar aur blood pressure ke test hoye thay? Koi masla tou nahi aya?", "field": "current_pregnancy.sugar_bp_tests", "category": "second_third_trimester"},
            {"id": 21, "text": "aapko is masle ke liye koi dawai khaani parhti hai?", "field": "current_pregnancy.sugar_bp_medication", "category": "second_third_trimester", "condition": "if_sugar_bp_issue"},
            {"id": 22, "text": "Aap taqat ki dawain le rahi hain?", "field": "current_pregnancy.supplements", "category": "second_third_trimester"},
            {"id": 23, "text": "Kabhi khoon ya pani prnay ki shikayat hui ho", "field": "current_pregnancy.bleeding_water_leakage", "category": "second_third_trimester"},
            {"id": 24, "text": "abhi ka koi recent scan hai apke paas?", "field": "current_pregnancy.recent_scan", "category": "second_third_trimester", "condition": "if_third_trimester"},
            
            # Obstetric History - For one child (10 questions)
            {"id": 25, "text": "Bache ki umer kiya hai?", "field": "obstetric_history.single_child.age", "category": "obstetric_history_one_child"},
            {"id": 26, "text": "Larka hai ya larki?", "field": "obstetric_history.single_child.gender", "category": "obstetric_history_one_child"},
            {"id": 27, "text": "Poore dino per paida hoa tha?", "field": "obstetric_history.single_child.full_term", "category": "obstetric_history_one_child"},
            {"id": 28, "text": "Operation hua tha ya normal delivery?", "field": "obstetric_history.single_child.delivery_method", "category": "obstetric_history_one_child"},
            {"id": 29, "text": "Dardien khudi lagi thi ya lagwani pari thi? Kitna waqt laga bache ki padaish mein?", "field": "obstetric_history.single_child.normal_delivery_details", "category": "obstetric_history_one_child", "condition": "if_normal_delivery"},
            {"id": 30, "text": "Kis wajah se hua tha?", "field": "obstetric_history.single_child.operation_reason", "category": "obstetric_history_one_child", "condition": "if_operation"},
            {"id": 31, "text": "Kahan pr paidaish hui", "field": "obstetric_history.single_child.delivery_location", "category": "obstetric_history_one_child"},
            {"id": 32, "text": "Padaish ke baad apko ya bache ko masla tou nahi hoa?", "field": "obstetric_history.single_child.post_delivery_complications", "category": "obstetric_history_one_child"},
            {"id": 33, "text": "Bacha ab theek hai? School jata hai?", "field": "obstetric_history.single_child.current_status", "category": "obstetric_history_one_child"},
            {"id": 34, "text": "Kya is huml mein sugar, blood pressure ya khoon ka masla hoa? Ya koi aur masla jo aap batana chahein?", "field": "obstetric_history.single_child.pregnancy_complications", "category": "obstetric_history_one_child"},
            
            # Obstetric History - For 2 or more children (10 questions)
            {"id": 35, "text": "Bare bache se shoro ho kr sab bachon ki umar r jins btayen.", "field": "obstetric_history.multiple_children.children_info", "category": "obstetric_history_multiple_children"},
            {"id": 36, "text": "Kya aapke tamam bachay poore dino pe paida huay thay?", "field": "obstetric_history.multiple_children.all_full_term", "category": "obstetric_history_multiple_children"},
            {"id": 37, "text": "Kya sab bachay normal tareeqe se paida huay thay ya kisi ka operation (C-section) hoa tha?", "field": "obstetric_history.multiple_children.delivery_methods", "category": "obstetric_history_multiple_children"},
            {"id": 38, "text": "Aapke bachay kahan paida huay thay?", "field": "obstetric_history.multiple_children.delivery_locations", "category": "obstetric_history_multiple_children"},
            {"id": 39, "text": "Jin bachon ki normal delivery hui thi, kya un mein dardien khud lag gayi thi ya lagwani pari thi?", "field": "obstetric_history.multiple_children.normal_delivery_details", "category": "obstetric_history_multiple_children", "condition": "if_any_normal_delivery"},
            {"id": 40, "text": "Operation ki wajah kya thi?", "field": "obstetric_history.multiple_children.operation_reasons", "category": "obstetric_history_multiple_children", "condition": "if_any_operation"},
            {"id": 41, "text": "Delivery ke baad kisi bache ya aapko koi masla tou nahi hua tha?", "field": "obstetric_history.multiple_children.post_delivery_complications", "category": "obstetric_history_multiple_children"},
            {"id": 42, "text": "Kya aapke tamam bachay ab theek hain? Kya sab school jatay hain?", "field": "obstetric_history.multiple_children.current_status", "category": "obstetric_history_multiple_children"},
            {"id": 43, "text": "Kya kisi bhi huml ke dauran aapko sugar, blood pressure, ya khoon ka masla hua tha? Ya koi aur masla jo aap batana chahein?", "field": "obstetric_history.multiple_children.pregnancy_complications", "category": "obstetric_history_multiple_children"},
            
            # Gynecological History (2 questions)
            {"id": 44, "text": "Ap khandaani mansooba bandi k liye koi tareeq istemal kerti theen is se pehlay?", "field": "gynecological_history.contraception", "category": "gynecological_history"},
            {"id": 45, "text": "Kiya ap nay kabhi bachaydaani k munh ka muaaiana(pap smear) kerwaya hain?", "field": "gynecological_history.pap_smear", "category": "gynecological_history"},
            
            # Past Medical History (2 questions)
            {"id": 46, "text": "Kiya ap kisi maslay k liye koi dawayi khaa rahi hain?", "field": "past_medical_history.current_medications", "category": "past_medical_history"},
            {"id": 47, "text": "Kabhi sugar/Blood pressure/ dama/TB/Yarqan/dil ya gurdon ka masla tou nahin hua? yan koi aur masla jo aap batana chahein?", "field": "past_medical_history.previous_conditions", "category": "past_medical_history"},
            
            # Surgical History (1 question)
            {"id": 48, "text": "Apka kabhi kisi wajah se koi operation tou nae hua?", "field": "surgical_history.operations", "category": "surgical_history"},
            
            # Family History (2 questions)
            {"id": 49, "text": "Kiya apkay ya apkay shohar k khandan men kisi ko sugar, blood pressure, dil, TB, ya bachon men banawti naqais tou nahin hain?", "field": "family_history.medical_conditions", "category": "family_history"},
            {"id": 50, "text": "If twins then ask: Kya apkay khandaan men pehlay koi jurwan bachay hoye hain?", "field": "family_history.twins_history", "category": "family_history", "condition": "if_twins"},
            
            # Personal History (4 questions)
            {"id": 51, "text": "Aapko kisi cheez ya koi dawai se allergy tou nahi hai?", "field": "personal_history.allergies", "category": "personal_history"},
            {"id": 52, "text": "Maaf kijiye ga, kiya aap ya aap ka shohar cigarette noshi ya kisi qisam ka koi aur nasha karti hain?", "field": "personal_history.smoking_substance_use", "category": "personal_history"},
            {"id": 53, "text": "Apkay sath ghar per koi gali galoch/ mar peet ya zabardasti tou nahin kerta?", "field": "personal_history.domestic_violence", "category": "personal_history"},
            {"id": 54, "text": "Apki ghiza kesi hai? Khaane mein phal, sabzian, gosht aur anday doodh ka istemaal karti hain?", "field": "personal_history.diet", "category": "personal_history"}
        ]
    
    def _initialize_patient_data(self, patient_id: str) -> Dict[str, Any]:
        """Initialize new patient data structure with all structured fields"""
        return {
            "patient_id": patient_id,
            "demographics": {
                "name": "",
                "age": "",
                "phone_number": "",
                "marriage_info": "",
                "marriage_duration": "",
                "consanguineous_marriage": False,
                "pregnancy_number": "",
                "number_of_children": 0,
                "first_pregnancy": False,
                "miscarriages_deaths": "",
                "last_menstrual_period": "",
                "last_menstrual_period_remembered": False,
                "regular_periods": ""
            },
            "problem_description": "",
            "detected_issue": "",  # Store which specific issue was detected
            "issue_specific_questions": {},  # Store answers to issue-specific questions
            "issue_specific_question_index": 0,  # Track which issue-specific question we're on
            "issue_specific_questions_complete": False,  # Flag to track if issue-specific questions are done
            "current_pregnancy": {
                "pregnancy_month": "",
                "trimester": "",
                "conception_method": "",
                "discovery_method": "",
                "early_ultrasound": False,
                "folic_acid": False,
                "early_symptoms": "",
                "fetal_movement": "",
                "anatomy_scan": False,
                "regular_checkup": False,
                "blood_urine_tests": "",
                "hb_level_symptoms": "",
                "sugar_bp_tests": "",
                "sugar_bp_medication": "",
                "supplements": False,
                "bleeding_water_leakage": "",
                "recent_scan": "",
                "has_twins": False
            },
            "obstetric_history": {
                "single_child": {
                    "age": "",
                    "gender": "",
                    "full_term": "",
                    "delivery_method": "",
                    "normal_delivery_details": "",
                    "operation_reason": "",
                    "delivery_location": "",
                    "post_delivery_complications": "",
                    "current_status": "",
                    "pregnancy_complications": ""
                },
                "multiple_children": {
                    "children_info": "",
                    "all_full_term": "",
                    "delivery_methods": "",
                    "delivery_locations": "",
                    "normal_delivery_details": "",
                    "operation_reasons": "",
                    "post_delivery_complications": "",
                    "current_status": "",
                    "pregnancy_complications": ""
                }
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
                "smoking_substance_use": "",
                "domestic_violence": "",
                "diet": ""
            },
            "socio_economic": {
                "husband_occupation": ""
            },
            "additional_info": "",
            "conversation_history": [],
            "current_phase": "onboarding",
            "current_question_index": 0,
            "assessment_complete": False,
            "alert_level": None,
            "visit_number": 1,
            "visit_history": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    async def _extract_information_intelligently(self, patient_text: str, patient_data: Dict[str, Any], current_question: Dict[str, Any]) -> bool:
        """Extract information from patient response and save to structured field. Returns True if valid answer extracted."""
        
        field_path = current_question.get("field", "")
        question_text = current_question.get("text", "")
        
        # Check if response is empty or just apologies/confusion
        patient_text_lower = patient_text.lower().strip()
        apology_keywords = ["sorry", "معذرت", "maaf", "samajh nahi aya", "سمجھ نہیں", "dubara", "دوبارہ", "nahi pata", "نہیں پتہ"]
        is_apology_or_confusion = any(keyword in patient_text_lower for keyword in apology_keywords) and len(patient_text.strip()) < 50
        
        if is_apology_or_confusion:
            print(f"⚠️ Patient response appears to be an apology/confusion, not extracting")
            return False
        
        extraction_prompt = f"""
        You are a medical assistant extracting structured information from patient responses.
        
        CURRENT QUESTION: "{question_text}"
        PATIENT RESPONSE: "{patient_text}"
        FIELD TO EXTRACT: "{field_path}"
        
        Extract the answer from the patient's response and format it appropriately based on the field type:
        
        - For text fields: Return the extracted text directly (even if partial or incomplete)
        - For boolean fields: Return true/false (infer from yes/no/positive/negative responses)
        - For numeric fields: Return the number (extract any number mentioned)
        - For date fields: Return the date in ISO format if possible
        
        IMPORTANT RULES:
        1. Be LENIENT - accept partial answers, variations, and informal responses
        2. If the patient gives ANY relevant information, extract it (even if not perfect)
        3. If the response is clearly an answer (not an apology or "I don't know"), extract it
        4. Extract ONLY the information relevant to this specific question
        5. If the response contains the answer in any form, extract it with confidence
        
        Return as JSON:
        {{
            "value": "extracted value here",
            "confidence": "high/medium/low",
            "is_valid_answer": true or false
        }}
        
        Set "is_valid_answer" to:
        - true: If the response contains an actual answer (even if partial)
        - false: Only if the response is clearly "I don't know", "I don't remember", or just an apology
        
        Examples:
        - Question: "Aapki umar kitni hai?" Response: "Meri umar 25 saal hai" → {{"value": "25", "confidence": "high", "is_valid_answer": true}}
        - Question: "Pishaab ka test kiya tha?" Response: "Haan, kiya tha" → {{"value": true, "confidence": "high", "is_valid_answer": true}}
        - Question: "Aapka pura naam kya hai?" Response: "Fatima" → {{"value": "Fatima", "confidence": "high", "is_valid_answer": true}}
        - Question: "Aapki umar kitni hai?" Response: "Main nahi janti" → {{"value": "", "confidence": "low", "is_valid_answer": false}}
        
        Return ONLY valid JSON.
        """
        
        try:
            response = await self._call_openai_async(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                timeout=20.0
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            extracted_value = None
            is_valid_answer = True
            try:
                if "{" in response_text and "}" in response_text:
                    start_idx = response_text.find("{")
                    end_idx = response_text.rfind("}") + 1
                    json_text = response_text[start_idx:end_idx]
                    extracted_info = json.loads(json_text)
                    extracted_value = extracted_info.get("value", patient_text)
                    is_valid_answer = extracted_info.get("is_valid_answer", True)
                else:
                    # If no JSON, use raw response as fallback
                    extracted_value = patient_text
                    is_valid_answer = True
            except json.JSONDecodeError:
                # If JSON parsing fails, use raw response
                extracted_value = patient_text
                is_valid_answer = True
            
            # Only save if we got a valid answer
            if is_valid_answer and extracted_value and str(extracted_value).strip():
                self._save_to_field(patient_data, field_path, extracted_value)
                print(f"✅ Saved answer to {field_path}: {extracted_value}")
                return True
            else:
                print(f"⚠️ Extracted value is empty or invalid, not saving: {extracted_value}")
                return False
            
        except Exception as e:
            print(f"Error in extraction: {e}")
            # Fallback: Try to save raw response if it seems like an answer
            if patient_text.strip() and not is_apology_or_confusion:
                self._save_to_field(patient_data, field_path, patient_text)
                print(f"✅ Saved raw response as fallback to {field_path}: {patient_text}")
                return True
            return False
    
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
    
    def _get_field_value(self, patient_data: Dict[str, Any], field_path: str) -> Any:
        """Get value from nested field path like 'demographics.name' or 'current_pregnancy.urine_test'"""
        parts = field_path.split(".")
        
        if len(parts) == 1:
            # Top-level field
            return patient_data.get(field_path, "")
        else:
            # Nested field
            current = patient_data
            for part in parts[:-1]:
                if part not in current:
                    return ""
                current = current[part]
                if not isinstance(current, dict):
                    return ""
            
            # Get the final value
            return current.get(parts[-1], "")
    
    async def _determine_next_response(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the next response based on current phase and patient data"""
        
        current_phase = patient_data.get("current_phase", "onboarding")
        
        if current_phase == "onboarding":
            return await self._handle_onboarding_phase(patient_text, patient_data)
        elif current_phase == "demographics":
            return await self._handle_demographics_phase(patient_text, patient_data)
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
    
    async def _translate_name_to_english(self, name: str) -> str:
        """Translate patient name from Urdu/Roman Urdu to English"""
        if not name or not name.strip():
            return name
        
        # If name is already in English (only contains ASCII letters, spaces, hyphens), return as is
        if all(ord(c) < 128 or c in [' ', '-', "'"] for c in name):
            # Capitalize properly
            return ' '.join(word.capitalize() for word in name.strip().split())
        
        # Use OpenAI to translate name to English
        if settings.openai_api_key and len(settings.openai_api_key) > 10:
            try:
                prompt = f"""Translate this name to English. The name might be in Urdu script or Roman Urdu (English transliteration).

Name: "{name}"

Rules:
- If it's already in English (like "sadia", "fatima", "ali"), return it with proper capitalization (e.g., "Sadia", "Fatima", "Ali")
- If it's in Urdu script or Roman Urdu, translate it to standard English spelling
- Return ONLY the English name, no explanations, no quotes
- Use standard English name spellings (e.g., "Sadia" not "Sadiya", "Fatima" not "Fatimah" unless that's the actual spelling)

Examples:
- "صادیہ" or "sadia" → "Sadia"
- "فاطمہ" or "fatima" → "Fatima"
- "علی" or "ali" → "Ali"
- "مریم" or "maryam" → "Maryam"

Now translate: "{name}"
"""
                response = await self._call_openai_async(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=50,
                    timeout=15.0
                )
                
                translated_name = response.choices[0].message.content.strip()
                # Remove quotes if present
                translated_name = translated_name.strip('"').strip("'").strip()
                # Capitalize properly
                translated_name = ' '.join(word.capitalize() for word in translated_name.split())
                print(f"✅ Translated name '{name}' to English: '{translated_name}'")
                return translated_name
            except Exception as e:
                print(f"⚠️ Name translation failed: {e}, using original")
                return name.strip()
        
        return name.strip()
    
    async def _handle_demographics_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle demographics phase - ask questions 4-9"""
        
        current_question_index = patient_data.get("current_question_index", 0)
        
        # Ensure current_question_index is an integer
        try:
            if isinstance(current_question_index, str):
                current_question_index = int(current_question_index) if current_question_index.isdigit() else 0
            elif current_question_index is None:
                current_question_index = 0
            else:
                current_question_index = int(current_question_index)
        except (ValueError, TypeError):
            current_question_index = 0
        
        # Ensure we have a valid question index (skip conditional ones if needed)
        # This will skip Q6 if first pregnancy, Q8 if LMP remembered, etc.
        current_question_index = self._get_next_valid_question_index(current_question_index, patient_data)
        patient_data["current_question_index"] = current_question_index
        
        # Check if we've completed all demographics questions (Q4-9, indices 0-5)
        # If the next valid question is >= 6, we've passed Q9 and are done with demographics
        if current_question_index >= 6:
            # All demographics questions (4-9) completed, move to problem collection
            patient_data["current_phase"] = "problem_collection"
            response_text = "شکریہ! اب مجھے بتائیں کہ آپ کو کیا مسئلہ ہے؟ آپ کی کیا تکلیف ہے؟"
            
            return {
                "response_text": response_text,
                "next_phase": "problem_collection",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
        
        # Ask the current question (Q4-9, indices 0-5)
        # Ensure we're still within Q4-9 range
        if current_question_index < 6:
            current_question = self.questions[current_question_index]
            question_text = current_question["text"]
            
            return {
                "response_text": question_text,
                "next_phase": "demographics",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
        else:
            # Should not reach here, but handle gracefully
            patient_data["current_phase"] = "problem_collection"
            response_text = "شکریہ! اب مجھے بتائیں کہ آپ کو کیا مسئلہ ہے؟ آپ کی کیا تکلیف ہے؟"
            
            return {
                "response_text": response_text,
                "next_phase": "problem_collection",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
    
    async def _handle_onboarding_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle onboarding phase - collect name, age, phone"""
        
        demographics = patient_data.get("demographics", {})
        patient_text_lower = patient_text.lower().strip()
        
        # Collect name, age, phone
        # Name patterns
        name_patterns = [
            r"mera naam ([\w\s]+) hai",
            r"mara naam ([\w\s]+) hai", 
            r"naam ([\w\s]+) hai",
            r"name is ([\w\s]+)",
            r"my name is ([\w\s]+)"
        ]
        
        # Age patterns
        age_patterns = [
            r"umar ([\d]+)",
            r"age ([\d]+)",
            r"([\d]+) saal",
            r"([\d]+) years",
            r"meri umar ([\d]+)"
        ]
        
        # Phone patterns
        phone_patterns = [
            r"phone.*?([\d\s\+\-]+)",
            r"number.*?([\d\s\+\-]+)",
            r"([\d]{10,})"
        ]
        
        # Extract name
        if not demographics.get("name"):
            extracted_name = None
            for pattern in name_patterns:
                match = re.search(pattern, patient_text_lower, re.IGNORECASE)
                if match:
                    extracted_name = match.group(1).strip()
                    break
            
            if extracted_name:
                # Translate name to English
                translated_name = await self._translate_name_to_english(extracted_name)
                demographics["name"] = translated_name
                print(f"✅ Extracted name via pattern: {extracted_name} → {translated_name}")
            else:
                # Fallback: word after "naam"
                words = patient_text.split()
                for i, word in enumerate(words):
                    if word.lower() in ["naam", "name"] and i + 1 < len(words):
                        potential_name = words[i + 1].strip().rstrip(".,!?")
                        if potential_name and len(potential_name) > 2:
                            # Translate name to English
                            translated_name = await self._translate_name_to_english(potential_name)
                            demographics["name"] = translated_name
                            print(f"✅ Extracted name via fallback: {potential_name} → {translated_name}")
                            break
        
        # Extract age
        if not demographics.get("age"):
            extracted_age = None
            for pattern in age_patterns:
                match = re.search(pattern, patient_text_lower, re.IGNORECASE)
                if match:
                    extracted_age = match.group(1).strip()
                    break
            
            if extracted_age:
                # Ensure age is stored as integer
                try:
                    age_int = int(extracted_age)
                    demographics["age"] = age_int
                    print(f"✅ Extracted age via pattern: {age_int}")
                except ValueError:
                    demographics["age"] = extracted_age
                    print(f"✅ Extracted age via pattern (as string): {extracted_age}")
        
        # Extract phone
        if not demographics.get("phone_number"):
            extracted_phone = None
            for pattern in phone_patterns:
                match = re.search(pattern, patient_text_lower, re.IGNORECASE)
                if match:
                    extracted_phone = re.sub(r'[\s\-\+]', '', match.group(1).strip())
                    if len(extracted_phone) >= 10:  # Valid phone length
                        break
                    extracted_phone = None
            
            if extracted_phone:
                demographics["phone_number"] = extracted_phone
                print(f"✅ Extracted phone via pattern: {extracted_phone}")
        
        # Try AI extraction if OpenAI is available and something is still missing
        missing_fields = []
        if not demographics.get("name"):
            missing_fields.append("name")
        if not demographics.get("age"):
            missing_fields.append("age")
        if not demographics.get("phone_number"):
            missing_fields.append("phone_number")
        
        if missing_fields and settings.openai_api_key and len(settings.openai_api_key) > 10:
            extraction_prompt = f"""
            Extract basic demographics from this Urdu/English response: "{patient_text}"
            
            Extract ONLY these missing fields: {', '.join(missing_fields)}
            
            Extract:
            - Name (if mentioned) - look for words like "naam", "name", "mera naam", "my name". Extract the name as provided (can be Urdu, Roman Urdu, or English)
            - Age (if mentioned) - look for numbers with "umar", "age", "saal", "years". Return as a number (e.g., 25 not "25")
            - Phone number (if mentioned) - look for digits in phone format (usually 10-12 digits)
            
            Return JSON: {{"name": "", "age": "", "phone_number": ""}}
            
            Examples:
            - "mera naam sadia hai" → {{"name": "sadia"}}
            - "meri umar 25 hai" → {{"age": 25}}
            - "mera phone 923001234567 hai" → {{"phone_number": "923001234567"}}
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
                        # Translate name to English
                        translated_name = await self._translate_name_to_english(extracted["name"])
                        demographics["name"] = translated_name
                        print(f"✅ Extracted name via AI: {extracted['name']} → {translated_name}")
                    if extracted.get("age") and not demographics.get("age"):
                        # Ensure age is stored as integer
                        try:
                            age_int = int(extracted["age"])
                            demographics["age"] = age_int
                            print(f"✅ Extracted age via AI: {age_int}")
                        except ValueError:
                            demographics["age"] = extracted["age"]
                            print(f"✅ Extracted age via AI (as string): {extracted['age']}")
                    if extracted.get("phone_number") and not demographics.get("phone_number"):
                        demographics["phone_number"] = extracted["phone_number"]
                        print(f"✅ Extracted phone via AI: {extracted['phone_number']}")
            except Exception as e:
                print(f"⚠️ AI extraction failed: {e}")
        
        # Ensure demographics are properly updated in patient_data
        patient_data["demographics"] = demographics
        
        # Debug: Print current demographics status
        print(f"📊 Current demographics status:")
        print(f"  Name: {demographics.get('name', 'NOT SET')}")
        print(f"  Age: {demographics.get('age', 'NOT SET')}")
        print(f"  Phone: {demographics.get('phone_number', 'NOT SET')}")
        
        # Check what's missing
        missing_info = []
        if not demographics.get("name") or demographics.get("name") == "":
            missing_info.append("نام")
        if not demographics.get("age") or demographics.get("age") == "":
            missing_info.append("عمر")
        if not demographics.get("phone_number") or demographics.get("phone_number") == "":
            missing_info.append("فون نمبر")
        
        if missing_info:
            print(f"❌ Missing: {', '.join(missing_info)}")
            if not patient_data.get("has_greeted"):
                patient_data["has_greeted"] = True
                if "عمر" in missing_info[0]:
                    response_text = f"وعلیکم السلام! میں آپ کی گائناکالوجی کی مدد کرنے کے لئے ہوں۔ آپ کی عمر کتنی ہے؟"
                else:
                    response_text = f"وعلیکم السلام! میں آپ کی گائناکالوجی کی مدد کرنے کے لئے ہوں۔ براہ کرم مجھے اپنا {missing_info[0]} بتائیں۔"
            else:
                if "عمر" in missing_info[0]:
                    response_text = f"آپ کی عمر کتنی ہے؟"
                else:
                    response_text = f"براہ کرم مجھے اپنا {missing_info[0]} بتائیں۔"
            
            return {
                "response_text": response_text,
                "next_phase": "onboarding",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
        else:
            # Onboarding complete (name, age, phone), move to demographics phase (Q4-9)
            print(f"✅ Onboarding complete! Name: {demographics.get('name')}, Age: {demographics.get('age')}, Phone: {demographics.get('phone_number')}")
            patient_data["current_phase"] = "demographics"
            patient_data["current_question_index"] = 0  # Start with question 4 (index 0)
            patient_data["current_question_index"] = self._get_next_valid_question_index(0, patient_data)
            
            if patient_data["current_question_index"] < len(self.questions):
                first_question = self.questions[patient_data["current_question_index"]]["text"]
                name = demographics.get("name", "صاحبہ")
                response_text = f"{name} صاحبہ، آپ کا آن بورڈنگ مکمل ہو گیا ہے۔ اب میں آپ سے کچھ ضروری سوالات پوچھوں گی۔\n\n{first_question}"
            else:
                response_text = f"{demographics.get('name', 'صاحبہ')} صاحبہ، آپ کا آن بورڈنگ مکمل ہو گیا ہے۔"
            
            return {
                "response_text": response_text,
                "next_phase": "demographics",
                "patient_data": patient_data,
                "action": "continue_conversation"
            }
    
    def _detect_issue_type(self, problem_text: str) -> str:
        """Detect which specific issue the patient mentioned"""
        problem_lower = problem_text.lower()
        
        # Check for each issue type
        if any(word in problem_lower for word in ["شوگر", "shakkar", "diabetes", "diabetic", "شوگر تیز", "شوگر زیادہ"]):
            return "sugar_tez"
        elif any(word in problem_lower for word in ["بلڈ پریشر", "bp", "pressure", "tez", "کم", "بلوڈ پریشر زیادہ", "بلوڈ پریشر کم"]):
            return "blood_pressure"
        elif any(word in problem_lower for word in ["خون کی کمی", "anemia", "خون کی کمی", "hemoglobin کم", "hb کم"]):
            return "khoon_ki_kami"
        elif any(word in problem_lower for word in ["پانی پار رہا", "water leak", "amniotic", "پانی نکل", "پانی گر"]):
            return "pani_par_raha"
        elif any(word in problem_lower for word in ["خون پار رہا", "bleeding", "blood", "خون آ", "خون نکل"]):
            return "khoon_par_raha"
        elif any(word in problem_lower for word in ["درد", "pain", "takleef", "دھک"]):
            return "dard"
        elif any(word in problem_lower for word in ["اطلاق", "vomiting", "qay", "vomit"]):
            return "ultian"
        elif any(word in problem_lower for word in ["بخار", "fever", "tap", "temperature"]):
            return "bukhar"
        elif any(word in problem_lower for word in ["حرکت نہیں", "movement nahi", "بچے کی حرکت", "fetal movement"]):
            return "harkat_nahi"
        elif any(word in problem_lower for word in ["گروٹھ رک", "growth nahi", "بچے کی گروٹھ", "fetal growth"]):
            return "growth_ruki"
        elif any(word in problem_lower for word in ["چیک اپ", "check up", "معیاری چیک اپ", "examination", "normal check"]):
            return "checkup"
        else:
            return "checkup"  # Default to checkup if no specific issue detected
    
    def _get_issue_specific_questions(self, issue_type: str, patient_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get issue-specific questions based on detected issue"""
        questions = []
        pregnancy_number = patient_data.get("demographics", {}).get("pregnancy_number", 1)
        is_2nd_or_more = pregnancy_number and int(str(pregnancy_number).strip()) >= 2 if str(pregnancy_number).strip().isdigit() else False
        
        if issue_type == "sugar_tez":
            questions = [
                {"id": "sugar_1", "text": "کب سے ہو رہا یہ مسئلہ؟", "field": "issue_specific.sugar.duration"},
                {"id": "sugar_2", "text": "کونسی دوا لی رہیں ہیں؟", "field": "issue_specific.sugar.medications"},
                {"id": "sugar_3", "text": "ابی کنٹرول کیسا ہے؟", "field": "issue_specific.sugar.control"},
                {"id": "sugar_4", "text": "بچے پر شوگر کے کوئی اثرات ہوئے ہیں؟", "field": "issue_specific.sugar.baby_effects"}
            ]
        elif issue_type == "blood_pressure":
            questions = [
                {"id": "bp_1", "text": "کب سے ہو رہا ہے یہ مسئلہ؟", "field": "issue_specific.bp.duration"},
                {"id": "bp_2", "text": "کونسی دوا لی رہیں ہیں؟", "field": "issue_specific.bp.medications"},
                {"id": "bp_3", "text": "کنٹرول رہتا ہے؟", "field": "issue_specific.bp.control"},
                {"id": "bp_4", "text": "سر میں درد، آنکھوں کے آگے اندھیرا، سینے میں درد یا الٹی تو نہیں آتی؟", "field": "issue_specific.bp.symptoms"},
                {"id": "bp_5", "text": "پیشاب یا خون کے ٹیسٹ ہوئے ہیں؟", "field": "issue_specific.bp.tests"},
                {"id": "bp_6", "text": "بچے کی گروتھ پر کوئی اثر تو نہیں ہوا؟", "field": "issue_specific.bp.baby_growth"}
            ]
        elif issue_type == "khoon_ki_kami":
            questions = [
                {"id": "anemia_1", "text": "کب سے ہو رہا یہ مسئلہ؟", "field": "issue_specific.anemia.duration"},
            ]
            if is_2nd_or_more:
                questions.append({"id": "anemia_2", "text": "پچھلے حمل میں خون کی کمی تھی؟", "field": "issue_specific.anemia.previous_pregnancy"})
            questions.extend([
                {"id": "anemia_3", "text": "آئرن کی گولیاں، کالے ٹیکے یا خون لگا ہے کبھی؟", "field": "issue_specific.anemia.treatment"},
                {"id": "anemia_4", "text": "اگر ٹیکے یا خون لگا ہے تو کب لگا تھا؟", "field": "issue_specific.anemia.treatment_date", "condition": "if_treatment_yes"},
                {"id": "anemia_5", "text": "حمل یا ماہواری میں خون زیادہ تو نہیں پڑتا؟", "field": "issue_specific.anemia.bleeding"},
                {"id": "anemia_6", "text": "کوئی لمبا بخار یا TB تو نہیں ہوا؟", "field": "issue_specific.anemia.fever_tb"},
                {"id": "anemia_7", "text": "لمبے عرصے سے پیٹ تو نہیں خراب رہتا؟", "field": "issue_specific.anemia.stomach"},
                {"id": "anemia_8", "text": "خاندان میں کسی کو خون لگتا ہو؟", "field": "issue_specific.anemia.family_history"}
            ])
        elif issue_type == "pani_par_raha":
            questions = [
                {"id": "water_1", "text": "کتنی دیر سے پڑ رہا ہے؟", "field": "issue_specific.water.duration"},
                {"id": "water_2", "text": "پانی بہت زیادہ پڑ رہا ہے یا تھوڑا تھوڑا؟ شلوار کے پہنچے تک آیا ہے؟", "field": "issue_specific.water.amount"},
                {"id": "water_3", "text": "اگر بہت زیادہ پڑ رہا ہے تو کتنے پیڈ بھر چکی ہیں؟", "field": "issue_specific.water.pads", "condition": "if_heavy"},
                {"id": "water_4", "text": "کوئی درد، یا خون پڑا ہو یا بخار ہو ساتھ؟", "field": "issue_specific.water.symptoms"}
            ]
        elif issue_type == "khoon_par_raha":
            questions = [
                {"id": "bleeding_1", "text": "کب سے پڑ رہا ہے؟", "field": "issue_specific.bleeding.duration"},
                {"id": "bleeding_2", "text": "کتنے پیڈ بھر چکی ہیں؟", "field": "issue_specific.bleeding.pads"},
                {"id": "bleeding_3", "text": "ساتھ درد بھی ہو رہی ہے؟", "field": "issue_specific.bleeding.pain"},
                {"id": "bleeding_4", "text": "BP تیز ہوتا ہے؟", "field": "issue_specific.bleeding.bp"},
                {"id": "bleeding_5", "text": "بچے کی حرکت ٹھیک محسوس ہو رہی ہے؟", "field": "issue_specific.bleeding.movement"},
                {"id": "bleeding_6", "text": "آنکھوں کے آگے اندھیرا یا چکر چکر تو نہیں آ رہے؟", "field": "issue_specific.bleeding.dizziness"}
            ]
        elif issue_type == "dard":
            questions = [
                {"id": "pain_1", "text": "کہاں پر درد ہو رہی ہے؟", "field": "issue_specific.pain.location"},
                {"id": "pain_2", "text": "کب سے ہو رہی ہے درد؟", "field": "issue_specific.pain.duration"},
                {"id": "pain_3", "text": "اگر نالوں میں ہو رہی ہے تو مسلسل درد ہو رہی ہے یا رک رک کر؟", "field": "issue_specific.pain.continuous", "condition": "if_naalon"}
            ]
        elif issue_type == "ultian":
            questions = [
                {"id": "vomit_1", "text": "کب سے آ رہیں ہیں؟", "field": "issue_specific.vomiting.duration"},
                {"id": "vomit_2", "text": "دن میں کتنی الٹیاں کرتی ہیں؟", "field": "issue_specific.vomiting.frequency"},
                {"id": "vomit_3", "text": "کونسی دوا استعمال کرتی ہیں؟", "field": "issue_specific.vomiting.medications"},
                {"id": "vomit_4", "text": "BP ٹھیک رہتا ہے؟", "field": "issue_specific.vomiting.bp"}
            ]
        elif issue_type == "bukhar":
            questions = [
                {"id": "fever_1", "text": "کب سے ہو رہا ہے؟", "field": "issue_specific.fever.duration"},
                {"id": "fever_2", "text": "تیز ہے یا ہلکا؟", "field": "issue_specific.fever.severity"},
                {"id": "fever_3", "text": "کپکپی کے ساتھ ہوتا ہے؟", "field": "issue_specific.fever.shivering"},
                {"id": "fever_4", "text": "ساتھ کوئی اور پیشاب، گلے یا پیٹ کا مسئلہ تو نہیں ہے؟", "field": "issue_specific.fever.other_symptoms"},
                {"id": "fever_5", "text": "پانی تو نہیں پڑا؟", "field": "issue_specific.fever.water_leak"}
            ]
        elif issue_type == "harkat_nahi":
            questions = [
                {"id": "movement_1", "text": "کب سے نہیں ہو رہی؟", "field": "issue_specific.movement.duration"},
                {"id": "movement_2", "text": "ایک گھنٹے میں کتنی دفعہ حرکت محسوس ہوئی؟", "field": "issue_specific.movement.frequency"}
            ]
        elif issue_type == "growth_ruki":
            questions = [
                {"id": "growth_1", "text": "کب سے رکی ہے؟", "field": "issue_specific.growth.duration"},
                {"id": "growth_2", "text": "اس کے لیے کوئی دوائیں آپ استعمال کر رہیں ہیں؟", "field": "issue_specific.growth.medications"},
                {"id": "growth_3", "text": "آپکو شوگر یا بلڈ پریشر تیز ہونے کا مسئلہ تو نہیں؟", "field": "issue_specific.growth.bp_sugar"}
            ]
        # For checkup, no issue-specific questions, go directly to regular questionnaire
        
        return questions
    
    async def _handle_problem_collection_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle problem collection phase - collect presenting complaint and ask issue-specific questions"""
        
        # Initialize issue_specific_questions if not exists
        if "issue_specific_questions" not in patient_data:
            patient_data["issue_specific_questions"] = {}
        if "issue_specific_question_index" not in patient_data:
            patient_data["issue_specific_question_index"] = 0
        if "issue_specific_questions_complete" not in patient_data:
            patient_data["issue_specific_questions_complete"] = False
        
        # If issue-specific questions are complete, move back to regular questionnaire (continue from question 10)
        if patient_data.get("issue_specific_questions_complete", False):
            patient_data["current_phase"] = "questionnaire"
            patient_data["current_question_index"] = 6  # Continue from question 10 (after questions 4-9)
            patient_data["current_question_index"] = self._get_next_valid_question_index(6, patient_data)
            return await self._handle_questionnaire_phase(patient_text, patient_data)
        
        # Check if we're in the middle of asking issue-specific questions
        detected_issue = patient_data.get("detected_issue", "")
        issue_questions = []
        if detected_issue:
            issue_questions = self._get_issue_specific_questions(detected_issue, patient_data)
            current_issue_index = patient_data.get("issue_specific_question_index", 0)
            
            # If we have issue-specific questions and haven't completed them
            if issue_questions and current_issue_index < len(issue_questions):
                # Save previous answer if this is not the first question and we have patient text
                if current_issue_index > 0 and patient_text.strip():
                    prev_question = issue_questions[current_issue_index - 1]
                    # Extract and save answer
                    field_path = prev_question.get("field", "")
                    if field_path:
                        self._save_to_field(patient_data, field_path, patient_text)
                        patient_data["issue_specific_questions"][prev_question["id"]] = patient_text
                
                # Find next question to ask (skip conditional ones if condition not met)
                while current_issue_index < len(issue_questions):
                    current_question = issue_questions[current_issue_index]
                    
                    # Check if this question has a condition
                    condition = current_question.get("condition")
                    should_ask = True
                    if condition:
                        if condition == "if_treatment_yes":
                            # Check if previous answer mentioned treatment
                            prev_answer = patient_data.get("issue_specific_questions", {}).get("anemia_3", "")
                            if "nahi" in prev_answer.lower() or "no" in prev_answer.lower() or not prev_answer or "na" in prev_answer.lower():
                                should_ask = False
                        elif condition == "if_heavy":
                            # Check if previous answer mentioned heavy leakage
                            prev_answer = patient_data.get("issue_specific_questions", {}).get("water_2", "")
                            if "thora" in prev_answer.lower() or "kam" in prev_answer.lower() or "thoda" in prev_answer.lower():
                                should_ask = False
                        elif condition == "if_naalon":
                            # Check if pain location is in naalon (lower abdomen/pelvis)
                            prev_answer = patient_data.get("issue_specific_questions", {}).get("pain_1", "")
                            if "naalon" not in prev_answer.lower() and "lower" not in prev_answer.lower() and "pait" not in prev_answer.lower():
                                should_ask = False
                    
                    if should_ask:
                        # Ask current question
                        response_text = current_question["text"]
                        patient_data["issue_specific_question_index"] = current_issue_index + 1
                        return {
                            "response_text": response_text,
                            "next_phase": "problem_collection",
                            "patient_data": patient_data,
                            "action": "continue_conversation"
                        }
                    else:
                        # Skip this question and move to next
                        current_issue_index += 1
                        patient_data["issue_specific_question_index"] = current_issue_index
                
                # If we've gone through all questions, save last answer and move to questionnaire
                if current_issue_index >= len(issue_questions):
                    # Save last answer if we have patient text
                    if patient_text.strip() and issue_questions:
                        last_question_index = current_issue_index - 1
                        if last_question_index >= 0 and last_question_index < len(issue_questions):
                            last_question = issue_questions[last_question_index]
                            field_path = last_question.get("field", "")
                            if field_path:
                                self._save_to_field(patient_data, field_path, patient_text)
                                patient_data["issue_specific_questions"][last_question["id"]] = patient_text
                    
                    patient_data["issue_specific_questions_complete"] = True
                    # Move to questionnaire and continue from question 10 (index 6)
                    patient_data["current_phase"] = "questionnaire"
                    patient_data["current_question_index"] = 6  # Continue from question 10 (after questions 4-9)
                    patient_data["current_question_index"] = self._get_next_valid_question_index(6, patient_data)
                    
                    # Get next regular question (question 10 onwards)
                    if patient_data["current_question_index"] < len(self.questions):
                        next_question = self.questions[patient_data["current_question_index"]]["text"]
                        response_text = f"شکریہ۔ اب میں آپ سے کچھ مزید سوالات پوچھوں گی۔\n\n{next_question}"
                    else:
                        # All questions done, move to assessment
                        patient_data["current_phase"] = "assessment"
                        assessment_result = await self._handle_assessment_phase("", patient_data)
                        return assessment_result
                    
                    return {
                        "response_text": response_text,
                        "next_phase": "questionnaire",
                        "patient_data": patient_data,
                        "action": "continue_conversation"
                    }
    
        # If we've completed all issue-specific questions
        if detected_issue and issue_questions:
            current_issue_index = patient_data.get("issue_specific_question_index", 0)
            
            # If we've reached the end, save last answer and move to questionnaire
            if current_issue_index >= len(issue_questions):
                # Save last answer if we have patient text
                if patient_text.strip() and issue_questions:
                    # Find the last question that was asked (index - 1)
                    last_question_index = current_issue_index - 1
                    if last_question_index >= 0 and last_question_index < len(issue_questions):
                        last_question = issue_questions[last_question_index]
                        field_path = last_question.get("field", "")
                        if field_path:
                            self._save_to_field(patient_data, field_path, patient_text)
                            patient_data["issue_specific_questions"][last_question["id"]] = patient_text
                
                patient_data["issue_specific_questions_complete"] = True
                # Move to questionnaire and continue from question 10 (index 6)
                patient_data["current_phase"] = "questionnaire"
                patient_data["current_question_index"] = 6  # Continue from question 10 (after questions 4-9)
                patient_data["current_question_index"] = self._get_next_valid_question_index(6, patient_data)
                
                # Get next regular question (question 10 onwards)
                if patient_data["current_question_index"] < len(self.questions):
                    next_question = self.questions[patient_data["current_question_index"]]["text"]
                    response_text = f"شکریہ۔ اب میں آپ سے کچھ مزید سوالات پوچھوں گی۔\n\n{next_question}"
                    
                    return {
                        "response_text": response_text,
                        "next_phase": "questionnaire",
                        "patient_data": patient_data,
                        "action": "continue_conversation"
                    }
                else:
                    # All questions done, move to assessment
                    patient_data["current_phase"] = "assessment"
                    assessment_result = await self._handle_assessment_phase("", patient_data)
                    return assessment_result
        
        # If problem not collected yet
        if not patient_data.get("problem_description"):
            # Extract problem from response
            if patient_text.strip():
                problem_text = patient_text.strip()
                patient_data["problem_description"] = problem_text
                print(f"✅ Saved problem description: {patient_data['problem_description']}")
                
                # Detect issue type
                detected_issue = self._detect_issue_type(problem_text)
                patient_data["detected_issue"] = detected_issue
                print(f"✅ Detected issue type: {detected_issue}")
                
                # Initialize issue-specific questions tracking
                if "issue_specific_questions" not in patient_data:
                    patient_data["issue_specific_questions"] = {}
                if "issue_specific_question_index" not in patient_data:
                    patient_data["issue_specific_question_index"] = 0
                if "issue_specific_questions_complete" not in patient_data:
                    patient_data["issue_specific_questions_complete"] = False
                
                # Check if we need to ask issue-specific questions
                issue_questions = self._get_issue_specific_questions(detected_issue, patient_data)
                
                if issue_questions and detected_issue != "checkup":
                    # Ask issue-specific questions first
                    # Stay in problem_collection phase to ask issue-specific questions
                    current_issue_index = 0
                    patient_data["issue_specific_question_index"] = current_issue_index
                    
                    # Find first question to ask (skip conditional ones if condition not met)
                    while current_issue_index < len(issue_questions):
                        current_question = issue_questions[current_issue_index]
                        condition = current_question.get("condition")
                        should_ask = True
                        
                        if condition:
                            if condition == "if_treatment_yes":
                                # This will be checked when we have previous answers
                                should_ask = True  # Will be handled dynamically
                            elif condition == "if_heavy":
                                # This will be checked when we have previous answers
                                should_ask = True  # Will be handled dynamically
                            elif condition == "if_naalon":
                                # This will be checked when we have previous answers
                                should_ask = True  # Will be handled dynamically
                        
                        if should_ask:
                            response_text = current_question["text"]
                            patient_data["issue_specific_question_index"] = current_issue_index + 1
                            return {
                                "response_text": response_text,
                                "next_phase": "problem_collection",
                                "patient_data": patient_data,
                                "action": "continue_conversation"
                            }
                        else:
                            current_issue_index += 1
                    
                    # If no questions to ask, move to questionnaire
                    patient_data["issue_specific_questions_complete"] = True
                    patient_data["current_phase"] = "questionnaire"
                    patient_data["current_question_index"] = 6  # Start from Q10 (index 6)
                    patient_data["current_question_index"] = self._get_next_valid_question_index(6, patient_data)
                    
                    if patient_data["current_question_index"] < len(self.questions):
                        first_question = self.questions[patient_data["current_question_index"]]["text"]
                        response_text = first_question
                    else:
                        response_text = "شکریہ۔ تمام سوالات مکمل ہو گئے ہیں۔"
                    
                    return {
                        "response_text": response_text,
                        "next_phase": "questionnaire",
                        "patient_data": patient_data,
                        "action": "continue_conversation"
                    }
                else:
                    # No issue-specific questions, move directly to questionnaire (Q10 onwards)
                    patient_data["current_phase"] = "questionnaire"
                    patient_data["current_question_index"] = 6  # Start from Q10 (index 6)
                    patient_data["current_question_index"] = self._get_next_valid_question_index(6, patient_data)
                    
                    if patient_data["current_question_index"] < len(self.questions):
                        first_question = self.questions[patient_data["current_question_index"]]["text"]
                        response_text = f"شکریہ۔ اب میں آپ سے کچھ مزید سوالات پوچھوں گی۔\n\n{first_question}"
                    else:
                        response_text = "شکریہ۔ تمام سوالات مکمل ہو گئے ہیں۔"
                    
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
            # Problem already collected but issue-specific questions not handled properly
            # This shouldn't happen, but handle it gracefully
            patient_data["current_phase"] = "questionnaire"
            patient_data["current_question_index"] = 0
            patient_data["current_question_index"] = self._get_next_valid_question_index(0, patient_data)
            return await self._handle_questionnaire_phase(patient_text, patient_data)
    
    async def _extract_pregnancy_month(self, patient_text: str, patient_data: Dict[str, Any]):
        """Extract pregnancy month from question 9 response and determine trimester"""
        
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
            response = await self._call_openai_async(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                timeout=20.0
            )
            
            response_text = response.choices[0].message.content.strip()
            if "{" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                extracted = json.loads(response_text[start_idx:end_idx])
                
                pregnancy_month = extracted.get("pregnancy_month", 0)
                
                # Ensure pregnancy_month is an integer
                try:
                    if isinstance(pregnancy_month, str):
                        pregnancy_month = int(pregnancy_month) if pregnancy_month.isdigit() else 0
                    else:
                        pregnancy_month = int(pregnancy_month) if pregnancy_month else 0
                except (ValueError, TypeError):
                    pregnancy_month = 0
                
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
                patient_data["current_pregnancy"] = current_pregnancy
                
                print(f"✅ Extracted pregnancy month: {pregnancy_month}, trimester: {trimester}")
                print(f"✅ Updated patient_data with trimester: {trimester}")
        except Exception as e:
            print(f"Error extracting pregnancy month: {e}")
    
    async def _extract_pregnancy_number(self, patient_text: str, patient_data: Dict[str, Any]):
        """Extract pregnancy number from question 5 response, determine if first pregnancy, and check for twins"""
        
        demographics = patient_data.get("demographics", {})
        current_pregnancy = patient_data.get("current_pregnancy", {})
        pregnancy_number = demographics.get("pregnancy_number", "")
        
        # Try to extract number from text
        import re
        numbers = re.findall(r'\d+', patient_text)
        if numbers:
            try:
                preg_num = int(numbers[0])
                demographics["pregnancy_number"] = str(preg_num)
                demographics["first_pregnancy"] = (preg_num == 1)
                # Calculate number_of_children from pregnancy_number
                # If 1st pregnancy → 0 children, 2nd pregnancy → 1 child, 3rd pregnancy → 2 children, etc.
                demographics["number_of_children"] = max(0, preg_num - 1)
                print(f"✅ Extracted pregnancy number: {preg_num}, first_pregnancy: {preg_num == 1}, number_of_children: {demographics['number_of_children']}")
            except:
                pass
        
        # Also check for "pehla", "first" keywords (but not "jurwan" alone as it can mean twins)
        patient_text_lower = patient_text.lower()
        first_pregnancy_keywords = ["pehla", "pehli", "first", "1st", "ek", "pehla hai", "pehli hai", "pehla hamal", "pehli hamal"]
        if any(keyword in patient_text_lower for keyword in first_pregnancy_keywords):
            if not demographics.get("pregnancy_number"):
                demographics["pregnancy_number"] = "1"
                demographics["first_pregnancy"] = True
                demographics["number_of_children"] = 0  # First pregnancy means 0 children
                print(f"✅ Detected first pregnancy from keywords, number_of_children: 0")
        
        # Check for twins in the response (more specific keywords to avoid confusion)
        twins_keywords = ["jurwan bachy", "jurwan bachay", "joorwan bachy", "joorwan bachay", "jurwan bache", "joorwan bache", 
                         "twins", "do bache", "2 bache", "dual", "multiple", "do bache ek sath", "do bachay ek sath",
                         "is hamal mein jurwan", "is hamal mein joorwan", "jurwan hain", "joorwan hain"]
        has_twins_mentioned = any(keyword in patient_text_lower for keyword in twins_keywords)
        
        if has_twins_mentioned:
            current_pregnancy["has_twins"] = True
            print(f"✅ Detected twins from question 5 response")
        
        patient_data["demographics"] = demographics
        patient_data["current_pregnancy"] = current_pregnancy
    
    def _calculate_pregnancy_weeks(self, lmp_date_str: str) -> Optional[Dict[str, Any]]:
        """Calculate pregnancy weeks and days from LMP date to current date"""
        try:
            # Try to parse the date string
            # Handle various date formats
            lmp_date = None
            
            # Try dateutil parser first (handles many formats)
            if DATEUTIL_AVAILABLE:
                try:
                    lmp_date = parser.parse(lmp_date_str, dayfirst=True, fuzzy=True)
                except:
                    pass
            
            # If that fails, try manual parsing
            if not lmp_date:
                # Try DD/MM/YYYY or DD-MM-YYYY
                date_patterns = [
                    r'(\d{1,2})[\s\-/](\d{1,2})[\s\-/](\d{2,4})',
                    r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{2,4})',
                ]
                
                months_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                
                for pattern in date_patterns:
                    match = re.search(pattern, lmp_date_str, re.IGNORECASE)
                    if match:
                        if len(match.groups()) == 3:
                            if match.group(2).lower() in months_map:
                                # Month name format
                                day = int(match.group(1))
                                month = months_map[match.group(2).lower()]
                                year = int(match.group(3))
                                if year < 100:
                                    year += 2000
                                lmp_date = datetime(year, month, day)
                            else:
                                # DD/MM/YYYY format
                                day = int(match.group(1))
                                month = int(match.group(2))
                                year = int(match.group(3))
                                if year < 100:
                                    year += 2000
                                lmp_date = datetime(year, month, day)
                            break
            
            if not lmp_date:
                print(f"⚠️ Could not parse LMP date: {lmp_date_str}")
                return None
            
            # Calculate difference from LMP to today
            today = datetime.now()
            delta = today - lmp_date
            
            # Calculate weeks and days
            total_days = delta.days
            weeks = total_days // 7
            days = total_days % 7
            
            # Calculate estimated due date (EDD) - 40 weeks from LMP
            edd = lmp_date + timedelta(days=280)  # 40 weeks = 280 days
            
            # Calculate gestational age
            gestational_age_weeks = weeks
            gestational_age_days = days
            
            result = {
                "lmp_date": lmp_date.strftime("%Y-%m-%d"),
                "lmp_date_display": lmp_date.strftime("%d/%m/%Y"),
                "current_date": today.strftime("%Y-%m-%d"),
                "current_date_display": today.strftime("%d/%m/%Y"),
                "pregnancy_weeks": weeks,
                "pregnancy_days": days,
                "total_days": total_days,
                "gestational_age_weeks": gestational_age_weeks,
                "gestational_age_days": gestational_age_days,
                "gestational_age_display": f"{weeks} weeks {days} days",
                "estimated_due_date": edd.strftime("%Y-%m-%d"),
                "estimated_due_date_display": edd.strftime("%d/%m/%Y"),
                "trimester": "first" if weeks < 14 else ("second" if weeks < 28 else "third")
            }
            
            print(f"✅ Calculated pregnancy: {weeks} weeks {days} days (from LMP: {lmp_date.strftime('%d/%m/%Y')})")
            return result
            
        except Exception as e:
            print(f"⚠️ Error calculating pregnancy weeks: {e}")
            return None
    
    async def _extract_lmp_info(self, patient_text: str, patient_data: Dict[str, Any]):
        """Extract LMP date and check if it was remembered"""
        
        demographics = patient_data.get("demographics", {})
        
        # Check if patient provided a date
        import re
        # Look for date patterns
        date_patterns = [
            r'\d{1,2}[\s\-/]\d{1,2}[\s\-/]\d{2,4}',  # DD/MM/YYYY
            r'\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        ]
        
        has_date = False
        for pattern in date_patterns:
            if re.search(pattern, patient_text, re.IGNORECASE):
                has_date = True
                break
        
        # Check for "yaad nahi", "remember nahi", "bhool gaya" etc.
        patient_text_lower = patient_text.lower()
        not_remembered_keywords = ["yaad nahi", "remember nahi", "bhool", "forgot", "pata nahi", "maloom nahi"]
        not_remembered = any(keyword in patient_text_lower for keyword in not_remembered_keywords)
        
        if has_date and not not_remembered:
            demographics["last_menstrual_period_remembered"] = True
            demographics["last_menstrual_period"] = patient_text.strip()
            
            # Calculate pregnancy weeks from LMP
            pregnancy_calc = self._calculate_pregnancy_weeks(patient_text.strip())
            if pregnancy_calc:
                demographics["pregnancy_calculation"] = pregnancy_calc
                # Also update current_pregnancy with calculated values
                current_pregnancy = patient_data.get("current_pregnancy", {})
                current_pregnancy["gestational_age_weeks"] = pregnancy_calc["gestational_age_weeks"]
                current_pregnancy["gestational_age_days"] = pregnancy_calc["gestational_age_days"]
                current_pregnancy["gestational_age_display"] = pregnancy_calc["gestational_age_display"]
                current_pregnancy["estimated_due_date"] = pregnancy_calc["estimated_due_date"]
                current_pregnancy["estimated_due_date_display"] = pregnancy_calc["estimated_due_date_display"]
                # Update trimester if not already set or if calculated is more accurate
                if not current_pregnancy.get("trimester") or pregnancy_calc["trimester"]:
                    current_pregnancy["trimester"] = pregnancy_calc["trimester"]
                patient_data["current_pregnancy"] = current_pregnancy
            
            print(f"✅ LMP date remembered: {patient_text.strip()}")
        elif not_remembered:
            demographics["last_menstrual_period_remembered"] = False
            print(f"✅ LMP date not remembered")
        
        patient_data["demographics"] = demographics
    
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
            response = await self._call_openai_async(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                timeout=20.0
            )
            
            response_text = response.choices[0].message.content.strip()
            if "{" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                extracted = json.loads(response_text[start_idx:end_idx])
                
                demographics = patient_data.get("demographics", {})
                number_of_children = extracted.get("number_of_children", 0)
                # Ensure it's an integer
                try:
                    number_of_children = int(number_of_children) if number_of_children else 0
                except (ValueError, TypeError):
                    number_of_children = 0
                demographics["number_of_children"] = number_of_children
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
            response = await self._call_openai_async(
                model="gpt-4",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                timeout=20.0
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
    
    async def _handle_recent_scan_followup(self, patient_text: str, patient_data: Dict[str, Any]):
        """Handle follow-up question for Q24 (recent scan) - if yes, ask about any problems"""
        
        current_pregnancy = patient_data.get("current_pregnancy", {})
        patient_text_lower = patient_text.lower().strip()
        
        # Check if patient said yes to having a recent scan
        yes_keywords = ["haan", "yes", "hain", "hai", "hoga", "karaya", "karwaya", "karwaya hai", "karaya hai", "hain", "kiya", "kiya hai"]
        no_keywords = ["nahi", "no", "na", "nhi", "nahi hai", "na hai"]
        
        # Check the extracted value first (from _extract_information_intelligently)
        recent_scan_value = current_pregnancy.get("recent_scan", "")
        recent_scan_answer = str(recent_scan_value).strip().lower() if recent_scan_value is not None else ""
        
        # Determine if answer is yes
        has_recent_scan = False
        if recent_scan_answer:
            # Check extracted value
            has_recent_scan = any(keyword in recent_scan_answer for keyword in yes_keywords) and not any(keyword in recent_scan_answer for keyword in no_keywords)
        else:
            # Check original text if extraction hasn't happened yet
            has_recent_scan = any(keyword in patient_text_lower for keyword in yes_keywords) and not any(keyword in patient_text_lower for keyword in no_keywords)
        
        # If patient said yes and we haven't asked the follow-up yet
        if has_recent_scan and not current_pregnancy.get("recent_scan_followup_asked", False):
            # Set flag to ask follow-up question
            current_pregnancy["recent_scan_followup_needed"] = True
            current_pregnancy["recent_scan_followup_asked"] = False  # Will be set to True after asking
            print(f"✅ Patient has recent scan, will ask follow-up question")
        else:
            # If they said no or we already asked, clear the flag
            current_pregnancy["recent_scan_followup_needed"] = False
        
        patient_data["current_pregnancy"] = current_pregnancy
    
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
        
        # Convert to int if it's a string (Firestore may store as string)
        try:
            if isinstance(pregnancy_month, str):
                pregnancy_month = int(pregnancy_month) if pregnancy_month.isdigit() else 0
            elif pregnancy_month is None:
                pregnancy_month = 0
            else:
                pregnancy_month = int(pregnancy_month)
        except (ValueError, TypeError):
            pregnancy_month = 0
        
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
        """Get the next valid question index with all conditional logic"""
        
        demographics = patient_data.get("demographics", {})
        current_pregnancy = patient_data.get("current_pregnancy", {})
        
        # Get pregnancy number and determine if first pregnancy
        pregnancy_number = demographics.get("pregnancy_number", "")
        first_pregnancy = demographics.get("first_pregnancy", False)
        
        # Determine if 2nd or more pregnancy
        is_2nd_or_more = False
        try:
            if pregnancy_number:
                preg_num = int(pregnancy_number) if str(pregnancy_number).isdigit() else 0
                is_2nd_or_more = preg_num >= 2
        except:
            pass
        
        # Get number of children - calculate from pregnancy_number if not already set
        number_of_children = demographics.get("number_of_children", 0)
        try:
            if isinstance(number_of_children, str):
                number_of_children = int(number_of_children) if number_of_children.isdigit() else 0
            elif number_of_children is None:
                number_of_children = 0
            else:
                number_of_children = int(number_of_children)
        except (ValueError, TypeError):
            number_of_children = 0
        
        # If number_of_children is 0 but we have pregnancy_number, calculate it
        # If 1st pregnancy → 0 children, 2nd pregnancy → 1 child, 3rd pregnancy → 2 children, etc.
        if number_of_children == 0 and pregnancy_number:
            try:
                preg_num = int(pregnancy_number) if str(pregnancy_number).isdigit() else 0
                if preg_num > 1:
                    number_of_children = preg_num - 1
                    demographics["number_of_children"] = number_of_children
                    print(f"✅ Calculated number_of_children from pregnancy_number: {preg_num} → {number_of_children}")
            except:
                pass
        
        # Check if LMP was remembered
        lmp_remembered = demographics.get("last_menstrual_period_remembered", False)
        if not lmp_remembered and demographics.get("last_menstrual_period"):
            # If LMP date is provided, assume it was remembered
            lmp_remembered = True
        
        # Get trimester
        trimester = self._get_pregnancy_trimester(patient_data)
        
        # Check if patient has twins
        has_twins = self._has_twins(patient_data)
        
        # Skip obstetric history if first pregnancy
        skip_obstetric_history = first_pregnancy or number_of_children == 0
        
        # Determine which obstetric history to use (1 child vs 2+ children)
        use_single_child_obstetric = number_of_children == 1
        use_multiple_children_obstetric = number_of_children >= 2
        
        # Check answers for conditional questions
        # Safely get string value (handle boolean/None cases)
        blood_test_value = current_pregnancy.get("blood_urine_tests", "")
        blood_test_answer = str(blood_test_value).strip() if blood_test_value is not None else ""
        blood_test_answered = bool(blood_test_answer and blood_test_answer.lower() not in ["", "none", "false"])  # Check if Q18 is answered
        
        sugar_bp_value = current_pregnancy.get("sugar_bp_tests", "")
        sugar_bp_answer = str(sugar_bp_value).strip().lower() if sugar_bp_value is not None else ""
        sugar_bp_issue = any(keyword in sugar_bp_answer for keyword in ["masla", "problem", "tez", "high", "issue", "problem hai", "masla hai"]) if sugar_bp_answer else False
        
        for i in range(start_index, len(self.questions)):
            question = self.questions[i]
            question_id = question.get("id", 0)
            condition = question.get("condition", "")
            
            # Ensure question_id is an integer
            try:
                if isinstance(question_id, str):
                    question_id = int(question_id) if question_id.isdigit() else 0
                elif question_id is None:
                    question_id = 0
                else:
                    question_id = int(question_id)
            except (ValueError, TypeError):
                question_id = 0
            
            # Condition 1: Question 6 (miscarriages/deaths) - only if 2nd+ pregnancy
            if question_id == 6 and not is_2nd_or_more:
                continue
            
            # Condition 2: Question 8 (regular periods) - only if LMP not remembered
            if question_id == 8 and lmp_remembered:
                continue
            
            # Condition 3: Skip obstetric history if first pregnancy
            if skip_obstetric_history:
                # Skip single child obstetric history (25-34)
                if 25 <= question_id <= 34:
                    continue
                # Skip multiple children obstetric history (35-43)
                if 35 <= question_id <= 43:
                    continue
            else:
                # If not first pregnancy, use appropriate obstetric history
                if use_single_child_obstetric and 35 <= question_id <= 43:
                    continue  # Skip multiple children questions
                if use_multiple_children_obstetric and 25 <= question_id <= 34:
                    continue  # Skip single child questions
            
            # Condition 4: Skip 2nd/3rd trimester questions (15-24) if in 1st trimester
            if trimester == "first" and 15 <= question_id <= 24:
                continue
            
            # Condition 4b: Skip 1st trimester questions (10-14) if in 2nd or 3rd trimester
            if trimester in ["second", "third"] and 10 <= question_id <= 14:
                continue
            
            # Condition 5: If 3rd trimester, ask 3rd trimester questions first (21-24), then 1st (10-14), then 2nd (15-20)
            # This is handled by the order in the questions list - 3rd trimester questions come after 2nd
            
            # Condition 6: Question 19 (Hb level) - only if Q18 (blood test) is answered
            if question_id == 19 and not blood_test_answered:
                continue  # Skip if blood test question (Q18) not answered yet
            
            # Condition 7: Question 21 (sugar/BP medication) - only if Q20 shows an issue
            if question_id == 21:
                sugar_bp_value = current_pregnancy.get("sugar_bp_tests", "")
                sugar_bp_answer = str(sugar_bp_value).strip() if sugar_bp_value is not None else ""
                if not sugar_bp_answer:
                    continue  # Skip if Q20 not answered yet
                # Check if answer indicates an issue
                answer_lower = sugar_bp_answer.lower()
                has_issue = any(keyword in answer_lower for keyword in ["masla", "problem", "tez", "high", "issue", "yes", "haan", "hua"])
                if not has_issue:
                    continue  # Skip if no issue detected
            
            # Condition 8: Question 24 (recent scan) - only if 3rd trimester
            if question_id == 24 and trimester != "third":
                continue
            
            # Condition 9: Question 50 (twins history) - only if twins
            if question_id == 50 and not has_twins:
                continue
            
            # Condition 10: Question 29 (normal delivery details) - only if normal delivery
            if question_id == 29:
                single_child = patient_data.get("obstetric_history", {}).get("single_child", {})
                delivery_method_value = single_child.get("delivery_method", "")
                delivery_method = str(delivery_method_value).strip().lower() if delivery_method_value is not None else ""
                if not delivery_method:
                    continue  # Skip if Q28 (delivery method) not answered yet
                if "normal" not in delivery_method:
                    continue  # Skip if not normal delivery
            
            # Condition 11: Question 30 (operation reason) - only if operation
            if question_id == 30:
                single_child = patient_data.get("obstetric_history", {}).get("single_child", {})
                delivery_method_value = single_child.get("delivery_method", "")
                delivery_method = str(delivery_method_value).strip().lower() if delivery_method_value is not None else ""
                if not delivery_method:
                    continue  # Skip if Q28 (delivery method) not answered yet
                # Skip if normal delivery (Q30 is only for operations)
                if "normal" in delivery_method:
                    continue
                # Skip if neither operation nor c-section mentioned
                if "operation" not in delivery_method and "c-section" not in delivery_method:
                    continue
            
            # Condition 12: Question 39 (normal delivery for multiple) - ONLY ask if normal delivery exists
            if question_id == 39:
                multiple_children = patient_data.get("obstetric_history", {}).get("multiple_children", {})
                delivery_methods_value = multiple_children.get("delivery_methods", "")
                delivery_methods = str(delivery_methods_value).strip().lower() if delivery_methods_value is not None else ""
                if not delivery_methods:
                    continue  # Skip if Q37 (delivery methods) not answered yet
                # Only ask if "normal" is mentioned - skip if no normal delivery
                if "normal" not in delivery_methods:
                    continue  # Skip if no normal delivery
            
            # Condition 13: Question 40 (operation reasons for multiple) - ONLY ask if operation/C-section exists
            if question_id == 40:
                multiple_children = patient_data.get("obstetric_history", {}).get("multiple_children", {})
                delivery_methods_value = multiple_children.get("delivery_methods", "")
                delivery_methods = str(delivery_methods_value).strip().lower() if delivery_methods_value is not None else ""
                if not delivery_methods:
                    continue  # Skip if Q37 (delivery methods) not answered yet
                # Only ask if "operation" or "c-section" is mentioned - skip if no operation
                if "operation" not in delivery_methods and "c-section" not in delivery_methods:
                    continue  # Skip if no operation/C-section
            
            return i
        
        # If no more valid questions, return the length (meaning we're done)
        return len(self.questions)
    
    async def _handle_questionnaire_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle questionnaire phase - ask all 60 questions sequentially, skipping irrelevant ones"""
        
        # Check if we need to ask follow-up question for Q24 (recent scan)
        current_pregnancy = patient_data.get("current_pregnancy", {})
        if current_pregnancy.get("recent_scan_followup_needed", False):
            if not current_pregnancy.get("recent_scan_followup_asked", False):
                # This is the first time - ask the follow-up question
                current_pregnancy["recent_scan_followup_asked"] = True
                patient_data["current_pregnancy"] = current_pregnancy
                response_text = "Koi masla tu nahi hai?"
                
                return {
                    "response_text": response_text,
                    "next_phase": "questionnaire",
                    "patient_data": patient_data,
                    "action": "continue_conversation"
                }
            else:
                # Follow-up was already asked, now store the answer and move to next question
                current_pregnancy["recent_scan_followup_answer"] = patient_text.strip()
                current_pregnancy["recent_scan_followup_needed"] = False
                current_pregnancy["recent_scan_followup_asked"] = False
                patient_data["current_pregnancy"] = current_pregnancy
                print(f"✅ Stored follow-up answer for recent scan: {patient_text}")
                
                # Now move to next question
                current_question_index = patient_data.get("current_question_index", 0)
                next_index = self._get_next_valid_question_index(current_question_index + 1, patient_data)
                patient_data["current_question_index"] = next_index
        
        # Note: Extraction and index increment already happened in process_patient_response (unless we handled follow-up above)
        current_question_index = patient_data.get("current_question_index", 0)
        
        # Note: Issue-specific questions are now handled in problem_collection phase
        # after problem is collected, so we don't need to check here
        
        # Ensure we have a valid question index (skip obstetric history if needed)
        current_question_index = self._get_next_valid_question_index(current_question_index, patient_data)
        patient_data["current_question_index"] = current_question_index
        
        # Check if we've completed all questions
        if current_question_index >= len(self.questions):
            # All questions answered, move to assessment and generate it immediately
            patient_data["current_phase"] = "assessment"
            
            # Immediately trigger assessment phase (don't wait for next patient message)
            assessment_result = await self._handle_assessment_phase(patient_text, patient_data)
            return assessment_result
        
        # Ask the current question
        current_question = self.questions[current_question_index]
        question_text = current_question["text"]
        
        # Special handling for question 19 - dynamic text based on blood_urine_tests
        if current_question.get("id") == 19:
            blood_test_value = current_pregnancy.get("blood_urine_tests", "")
            # Check if blood test was done (true/yes) or not (false/no)
            blood_test_done = False
            if isinstance(blood_test_value, bool):
                blood_test_done = blood_test_value
            elif isinstance(blood_test_value, str):
                blood_test_lower = str(blood_test_value).strip().lower()
                blood_test_done = any(word in blood_test_lower for word in ["yes", "haan", "hai", "hain", "kiya", "karaya", "true", "1"])
            
            if blood_test_done:
                # If blood test was done, ask about Hb level
                question_text = "Hb kitni hai?"
            else:
                # If blood test was not done, ask about symptoms
                question_text = "Kya aapko thakawat, saans ka phoolna, ya dil ki dharkan tez hone ka masla hota hai?"
        
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
        
        # Store assessment details in patient_data (for EMR, not sent to patient)
        patient_data["assessment_summary"] = assessment.get('assessment_summary', '')
        patient_data["clinical_impression"] = assessment.get('clinical_impression', '')
        
        # Generate response based on alert level (without assessment summary or alert level mention)
        if alert_level == "red":
            response_text = "فوراً ڈاکٹر کے پاس جائیں۔"
        elif alert_level == "yellow":
            response_text = "1 ہفتے کے اندر ڈاکٹر کے پاس ضرور جائیں۔"
        else:
            response_text = "2 ہفتوں کے اندر ڈاکٹر کو چیک کروا لیں۔"
        
        return {
            "response_text": response_text,
            "next_phase": "completed",
            "patient_data": patient_data,
            "action": "generate_emr"
        }
    
    def _convert_to_json_serializable(self, obj: Any) -> Any:
        """Convert Firestore datetime objects and other non-serializable types to JSON-serializable formats"""
        if hasattr(obj, 'isoformat'):  # DatetimeWithNanoseconds or datetime objects
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            # For any other type, convert to string
            return str(obj)
    
    async def _generate_assessment(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate medical assessment using AI based on all collected structured data"""
        
        assessment_prompt = f"""
        You are a FEMALE SENIOR PAKISTANI GYNECOLOGIST performing a comprehensive medical assessment.
        
        IMPORTANT: When responding in Urdu, use FEMALE-GENDERED verbs and forms:
        - Use "میں کر رہی ہوں" (I am doing) not "میں کر رہا ہوں"
        - Use "میں نے کیا" (I did) not "میں نے کیا" (same but context matters)
        - Use "میں سمجھ سکی" (I understood) not "میں سمجھ سکا"
        - Use "میں پوچھوں گی" (I will ask) not "میں پوچھوں گا"
        - Always speak as a female medical professional
        
        COMPLETE PATIENT INFORMATION:
        {json.dumps(self._convert_to_json_serializable(patient_data), ensure_ascii=False, indent=2)}
        
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
        
        IMPORTANT: All responses must be in ENGLISH for medical documentation purposes.
        
        Return as JSON:
        {{
            "alert_level": "red" or "yellow" or "green",
            "assessment_summary": "brief assessment summary in ENGLISH - professional medical language",
            "clinical_impression": "likely diagnosis or condition in ENGLISH - professional medical terminology",
            "recommendations": "what patient should do next in ENGLISH - clear medical recommendations"
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
                    return {"alert_level": "yellow", "assessment_summary": "Standard gynecological consultation - requires further evaluation", "clinical_impression": "Requires clinical evaluation", "recommendations": "Follow-up with healthcare provider recommended"}
            except json.JSONDecodeError:
                return {"alert_level": "yellow", "assessment_summary": "Standard gynecological consultation - requires further evaluation", "clinical_impression": "Requires clinical evaluation", "recommendations": "Follow-up with healthcare provider recommended"}
                
        except Exception as e:
            print(f"Error generating assessment: {e}")
            return {"alert_level": "yellow", "assessment_summary": "Standard gynecological consultation - requires further evaluation", "clinical_impression": "Requires clinical evaluation", "recommendations": "Follow-up with healthcare provider recommended"}
    
    async def _handle_completed_phase(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completed phase - conversation is done"""
        
        # Ensure assessment_complete is True and phase is completed (in case it wasn't set properly)
        patient_data["assessment_complete"] = True
        patient_data["current_phase"] = "completed"
        
        # Archive visit if it hasn't been archived yet
        visit_number = patient_data.get("visit_number", 1)
        visit_history = patient_data.get("visit_history", [])
        if not isinstance(visit_history, list):
            visit_history = []
        
        # Check if this visit has already been archived
        existing_visit = next((v for v in visit_history if v.get("visit_number") == visit_number), None)
        if not existing_visit:
            # Archive this visit
            await self._archive_current_visit(patient_data)
        
        response_text = "✅ آپ کا طبی رپورٹ تیار ہو گیا ہے۔ اللہ حافظ!"
        
        return {
            "response_text": response_text,
            "next_phase": "completed",
            "patient_data": patient_data,
            "action": "end_conversation"
        }
    
    async def _handle_general_response(self, patient_text: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general responses"""
        
        # Check if patient is returning after a completed visit
        if patient_data.get("current_phase") == "completed":
            await self._start_new_visit(patient_data)
        
        if not patient_data.get("has_greeted"):
            patient_data["has_greeted"] = True
            visit_number = patient_data.get("visit_number", 1)
            if visit_number > 1:
                response_text = f"وعلیکم السلام! آپ کا دوبارہ خیرمقدم ہے۔ یہ آپ کا {visit_number}واں دورہ ہے۔ براہ کرم مجھے اپنا نام بتائیں۔"
            else:
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
            
            # Get visit number for this EMR
            visit_number = emr_patient_data.get('visit_number', 1)
            
            # Calculate pregnancy weeks if LMP is available but calculation not done
            demographics = emr_patient_data.get('demographics', {})
            if demographics.get('last_menstrual_period') and not demographics.get('pregnancy_calculation'):
                lmp_date = demographics.get('last_menstrual_period')
                if lmp_date and isinstance(lmp_date, str):
                    pregnancy_calc = self._calculate_pregnancy_weeks(lmp_date)
                    if pregnancy_calc:
                        demographics['pregnancy_calculation'] = pregnancy_calc
                        emr_patient_data['demographics'] = demographics
                        # Also update current_pregnancy
                        current_pregnancy = emr_patient_data.get('current_pregnancy', {})
                        current_pregnancy["gestational_age_weeks"] = pregnancy_calc["gestational_age_weeks"]
                        current_pregnancy["gestational_age_days"] = pregnancy_calc["gestational_age_days"]
                        current_pregnancy["gestational_age_display"] = pregnancy_calc["gestational_age_display"]
                        current_pregnancy["estimated_due_date"] = pregnancy_calc["estimated_due_date"]
                        current_pregnancy["estimated_due_date_display"] = pregnancy_calc["estimated_due_date_display"]
                        emr_patient_data['current_pregnancy'] = current_pregnancy
            
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
            You are a senior gynecologist generating a comprehensive Electronic Medical Record (EMR) for a patient.
            
            CRITICAL REQUIREMENTS:
            - EVERYTHING must be written in PROFESSIONAL ENGLISH medical terminology
            - NO Urdu, Roman Urdu, or any other language - ONLY English
            - Use proper medical terminology and professional language throughout
            - Assessment summary, clinical impression, and all sections must be in English
            - Translate any Urdu/Roman Urdu patient responses to English medical terms
            
            Complete Patient Data: {json.dumps(self._convert_to_json_serializable(emr_patient_data), ensure_ascii=False, indent=2)}
            
            Create a detailed professional gynecological medical report using ALL the structured information collected from the 60-question questionnaire. 
            
            IMPORTANT: All content must be in English - translate patient responses from Urdu/Roman Urdu to proper English medical terminology.
            
            Include the following sections in EXACTLY this order:
            
            # ELECTRONIC MEDICAL RECORD (EMR)
            ## Gynecological Consultation Report
            
            **Visit Number:** {visit_number}
            
            ### 1. NAME
            Patient's full name: [Extract from demographics.name]
            
            ### 2. AGE
            Patient's age: [Extract from demographics.age]
            
            ### 3. PHONE NUMBER
            Contact number: [Extract from demographics.phone_number]
            
            ### 4. PRESENTING COMPLAINT
            Chief Complaint: {emr_patient_data.get('problem_description', 'Not specified')}
            
            **Issue-Specific Follow-up Details:**
            If the patient reported a specific issue (sugar/diabetes, blood pressure, anemia/khoon ki kami, bleeding/khoon par raha, water leakage/pani par raha, pain/dard, vomiting/ultian, fever/bukhar, reduced fetal movement, or growth restriction), you MUST include ALL the detailed follow-up questions and answers collected for that specific issue. 
            
            Look for the 'issue_specific' field in the patient data structure. It contains detailed information such as:
            - Duration of the issue
            - Medications being taken
            - Control/management status
            - Symptoms experienced
            - Tests performed
            - Impact on baby/fetus
            - Treatment history
            - Any other relevant details specific to that issue
            
            Present this information in a structured format. Translate all Urdu/Roman Urdu responses to professional English medical terminology. If no issue-specific questions were asked (e.g., for routine checkup), you can skip this subsection.
            
            ### 5. HOPI (History of Presenting Illness)
            Provide a detailed history of the presenting illness. Include:
            - Onset and duration of symptoms
            - Progression of the complaint
            - Associated symptoms
            - Aggravating and relieving factors
            - Any previous treatments or medications taken for this issue
            - Impact on daily activities
            - Any relevant timeline of events
            
            Use information from the presenting complaint and issue-specific questions to construct a comprehensive HOPI. Translate all Urdu/Roman Urdu responses to professional English medical terminology.
            
            ### 6. PREGNANCY
            Include all pregnancy-related details:
            - Current Trimester: [first/second/third]
            - Pregnancy month (if mentioned)
            - Conception method (natural/IVF/medication-assisted)
            - Discovery method
            - Early symptoms (nausea, vomiting, fever, bleeding)
            - Fetal movement details
            - Ultrasound/scan results (early ultrasound, anatomy scan, recent scans)
            - Regular checkups
            - Blood and urine tests
            - Hb levels and symptoms
            - Sugar and BP tests and any issues
            - Medications for sugar/BP if applicable
            - Supplements taken
            - Bleeding or water leakage issues
            - Any complications
            
            **PREGNANCY CALCULATION (if LMP date available):**
            If the patient provided their Last Menstrual Period (LMP) date, include:
            - LMP Date: [date in DD/MM/YYYY format]
            - Current Gestational Age: [X weeks Y days]
            - Estimated Due Date (EDD): [date in DD/MM/YYYY format]
            - Days since LMP: [total days]
            
            Use the pregnancy_calculation field from demographics if available, or calculate from LMP date if provided.
            
            ### 7. OBSTETRIC HISTORY
            Include complete obstetric history:
            - Number of previous pregnancies
            - Previous deliveries details
            - Birth weights (if mentioned)
            - Delivery methods (normal/operation/C-section)
            - Delivery locations
            - Normal delivery details (if applicable)
            - Operation reasons (if applicable)
            - Post-delivery complications
            - Current status of children
            - Pregnancy complications in previous pregnancies
            - Miscarriages or deaths (if applicable)
            
            If first pregnancy, state "Primigravida - No previous obstetric history"
            
            ### 8. GYNAECOLOGICAL HISTORY
            Include:
            - Contraception history (previous methods used)
            - Pap smear status
            - Menstrual history (LMP, regularity, etc.)
            - Any other gynecological procedures or conditions
            
            ### 9. MEDICAL HISTORY
            Include:
            - Current medications being taken
            - Previous medical conditions (diabetes, hypertension, TB, jaundice, heart or kidney issues, etc.)
            - Any chronic conditions
            - Medical conditions requiring ongoing treatment
            
            ### 10. SURGICAL HISTORY
            Include:
            - Previous operations and procedures
            - Dates and reasons for surgeries (if mentioned)
            - Any surgical complications
            
            ### 11. PREVIOUS MODE OF DELIVERY
            Extract and detail:
            - Delivery methods for all previous pregnancies
            - Normal deliveries: details about labor onset, duration, any interventions
            - Operations/C-sections: reasons, dates, any complications
            - Delivery locations
            - Post-delivery outcomes
            
            If first pregnancy, state "No previous deliveries"
            
            ### 12. FHx (FAMILY HISTORY)
            Include:
            - Medical conditions in patient's or husband's family
            - Conditions mentioned: diabetes, blood pressure, heart disease, TB, congenital anomalies in children
            - Twins history in family (if applicable)
            - Any hereditary conditions
            
            ### 13. PHx (PERSONAL HISTORY)
            Include:
            - Allergies (to medications, substances, etc.)
            - Smoking or substance use (patient or husband)
            - Domestic violence concerns
            - Diet and nutrition
            - Any other personal habits or lifestyle factors
            
            ### 14. SOCIOECONOMIC HISTORY
            Include:
            - Husband's occupation
            - Family size (if mentioned)
            - Living arrangements (if mentioned)
            - Any socioeconomic factors relevant to healthcare
            
            ### 15. ALERT LEVEL
            **Alert Level:** {alert_level.upper()}
            
            ---
            
            ### MEDICAL ASSESSMENT
            **Assessment Summary:** Write a comprehensive assessment summary in English. If the provided assessment_summary contains Urdu or non-English text, translate it to professional English medical terminology: {emr_patient_data.get('assessment_summary', 'Standard gynecological consultation')}
            **Clinical Impression:** Write clinical impression in English. If the provided clinical_impression contains Urdu or non-English text, translate it to professional English medical terminology: {emr_patient_data.get('clinical_impression', 'Requires further evaluation')}
            
            NOTE: Translate any Urdu/Roman Urdu text in assessment_summary or clinical_impression to proper English medical terminology.
            
            ### COMPREHENSIVE MEDICAL SUMMARY
            Generate a detailed clinical assessment in English that synthesizes ALL the collected information. Provide a thorough analysis of the patient's condition based on all 60 questions answered. Use professional medical terminology throughout. Translate any patient responses from Urdu/Roman Urdu to English.
            
            ### RECOMMENDATIONS
            Provide detailed recommendations in English for further care, follow-up, investigations, and treatment options based on the complete assessment. Use clear, professional medical language.
            
            ### FOLLOW-UP INSTRUCTIONS
            Clear follow-up instructions in English including when to return, what to monitor, and when to seek immediate care.
            
            REMEMBER: Every single word, sentence, and section must be in English. Translate any non-English content to proper English medical terminology.
            
            ---
            **Visit Number:** {visit_number}
            **Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            **Generated By:** AI Gynecological Assistant
            
            IMPORTANT: Use ALL the structured data collected. Don't leave out any important information. Format this as a professional medical report with proper markdown formatting, clear headings, and structured sections. Use bold text for field labels and maintain professional medical terminology throughout.
            """
            
            response = await self._call_openai_async(
                model="gpt-4",
                messages=[{"role": "user", "content": emr_prompt}],
                temperature=0.1,
                timeout=60.0  # EMR generation can take longer
            )
            
            # Get visit number for this EMR
            visit_number = emr_patient_data.get('visit_number', 1)
            
            emr_content = response.choices[0].message.content.strip()
            
            # Save EMR to Firestore
            emr_data = {
                "patient_id": patient_id,
                "visit_number": visit_number,
                "emr_content": emr_content,
                "alert_level": alert_level,
                "assessment_summary": emr_patient_data.get('assessment_summary', 'Standard gynecological consultation'),
                "clinical_impression": emr_patient_data.get('clinical_impression', 'Requires further evaluation'),
                "created_at": datetime.now().isoformat(),
                "patient_data": emr_patient_data
            }
            
            # Update patient data with the alert level and assessment
            # Ensure assessment_complete is True and phase is completed
            await self.firestore_service.update_patient(patient_id, {
                "alert_level": alert_level,
                "assessment_summary": emr_patient_data.get('assessment_summary', 'Standard gynecological consultation'),
                "clinical_impression": emr_patient_data.get('clinical_impression', 'Requires further evaluation'),
                "assessment_complete": True,
                "current_phase": "completed",  # Ensure phase is set to completed
                "updated_at": datetime.now().isoformat()
            })
            
            await self.firestore_service.create_emr(patient_id, emr_data)
            print(f"✅ EMR generated successfully with alert level: {alert_level}")
            return True
            
        except Exception as e:
            print(f"Error generating EMR: {e}")
            return False
    
    async def _archive_current_visit(self, patient_data: Dict[str, Any]):
        """Archive the current visit data to visit_history before starting a new visit"""
        try:
            visit_number = patient_data.get("visit_number", 1)
            
            # Check if this visit has already been archived
            visit_history = patient_data.get("visit_history", [])
            if not isinstance(visit_history, list):
                visit_history = []
            
            # Check if this visit number already exists in history
            existing_visit = next((v for v in visit_history if v.get("visit_number") == visit_number), None)
            if existing_visit:
                print(f"⚠️ Visit {visit_number} already archived, skipping")
                return
            
            # Create a copy of current visit data (excluding visit tracking fields)
            visit_data = {
                "visit_number": visit_number,
                "visit_date": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "alert_level": patient_data.get("alert_level"),
                "assessment_summary": patient_data.get("assessment_summary", ""),
                "clinical_impression": patient_data.get("clinical_impression", ""),
                "problem_description": patient_data.get("problem_description", ""),
                "demographics": patient_data.get("demographics", {}).copy() if isinstance(patient_data.get("demographics"), dict) else {},
                "current_pregnancy": patient_data.get("current_pregnancy", {}).copy() if isinstance(patient_data.get("current_pregnancy"), dict) else {},
                "obstetric_history": patient_data.get("obstetric_history", {}).copy() if isinstance(patient_data.get("obstetric_history"), dict) else {},
                "gynecological_history": patient_data.get("gynecological_history", {}).copy() if isinstance(patient_data.get("gynecological_history"), dict) else {},
                "past_medical_history": patient_data.get("past_medical_history", {}).copy() if isinstance(patient_data.get("past_medical_history"), dict) else {},
                "surgical_history": patient_data.get("surgical_history", {}).copy() if isinstance(patient_data.get("surgical_history"), dict) else {},
                "family_history": patient_data.get("family_history", {}).copy() if isinstance(patient_data.get("family_history"), dict) else {},
                "personal_history": patient_data.get("personal_history", {}).copy() if isinstance(patient_data.get("personal_history"), dict) else {},
                "socio_economic": patient_data.get("socio_economic", {}).copy() if isinstance(patient_data.get("socio_economic"), dict) else {},
                "additional_info": patient_data.get("additional_info", ""),
                "conversation_history": patient_data.get("conversation_history", []).copy() if isinstance(patient_data.get("conversation_history"), list) else []
            }
            
            # Add current visit to history
            visit_history.append(visit_data)
            patient_data["visit_history"] = visit_history
            
            print(f"✅ Archived visit {visit_number} to visit_history")
            
        except Exception as e:
            print(f"❌ Error archiving visit: {e}")
            import traceback
            traceback.print_exc()
    
    async def _start_new_visit(self, patient_data: Dict[str, Any]):
        """Start a new visit for a returning patient - reset conversation state but keep basic info"""
        try:
            # Archive the previous visit if it exists and hasn't been archived
            if patient_data.get("current_phase") == "completed" and patient_data.get("assessment_complete", False):
                await self._archive_current_visit(patient_data)
            
            # Get basic demographics to preserve
            demographics = patient_data.get("demographics", {})
            if not isinstance(demographics, dict):
                demographics = {}
            
            preserved_name = demographics.get("name", "")
            preserved_age = demographics.get("age", "")
            preserved_phone = demographics.get("phone_number", "")
            
            # Increment visit number
            current_visit = patient_data.get("visit_number", 1)
            new_visit = current_visit + 1
            patient_data["visit_number"] = new_visit
            
            # Initialize new visit data (reset everything except basic info)
            new_patient_data = self._initialize_patient_data(patient_data.get("patient_id", ""))
            
            # Preserve basic demographics
            new_patient_data["demographics"]["name"] = preserved_name
            new_patient_data["demographics"]["age"] = preserved_age
            new_patient_data["demographics"]["phone_number"] = preserved_phone
            
            # Preserve visit tracking
            new_patient_data["visit_number"] = new_visit
            new_patient_data["visit_history"] = patient_data.get("visit_history", [])
            
            # Preserve created_at (first visit date)
            new_patient_data["created_at"] = patient_data.get("created_at", datetime.now().isoformat())
            
            # Update patient_data with new visit data
            patient_data.update(new_patient_data)
            
            # Reset conversation state
            patient_data["current_phase"] = "onboarding"
            patient_data["current_question_index"] = 0
            patient_data["assessment_complete"] = False
            patient_data["alert_level"] = None
            patient_data["has_greeted"] = False  # Reset greeting so they get welcome message
            
            print(f"✅ Started new visit {new_visit} for patient {patient_data.get('patient_id')}")
            
        except Exception as e:
            print(f"❌ Error starting new visit: {e}")
            import traceback
            traceback.print_exc()
    
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
