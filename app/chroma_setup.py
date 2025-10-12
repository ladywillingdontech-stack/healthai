import chromadb
from chromadb.config import Settings
import openai
from typing import List, Dict, Any
import PyPDF2
import io
import json
from app.config import settings
from app.models import ChromaQuestion


class ChromaDBSetup:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="health_questions",
            metadata={"hnsw:space": "cosine"},
            embedding_function=None  # We'll provide our own embeddings
        )
        openai.api_key = settings.openai_api_key

    def parse_pdf_questions(self, pdf_path: str) -> List[ChromaQuestion]:
        """Parse PDF file and extract questions with metadata"""
        questions = []
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                lines = text.split('\n')
                
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if not line or len(line) < 10:
                        continue
                    
                    # Extract question metadata based on content patterns
                    question_data = self._extract_question_metadata(line, page_num, line_num)
                    if question_data:
                        questions.append(question_data)
        
        return questions

    def _extract_question_metadata(self, text: str, page_num: int, line_num: int) -> ChromaQuestion:
        """Extract metadata from question text"""
        question_id = f"q_{page_num}_{line_num}"
        
        # Determine question type based on keywords
        question_type = "onboarding"
        if any(keyword in text.lower() for keyword in ["age", "gender", "children", "marital"]):
            question_type = "demographic"
        elif any(keyword in text.lower() for keyword in ["pain", "symptom", "ache", "fever", "cough"]):
            question_type = "symptom"
        
        # Determine alert flag
        alert_flag = "none"
        if any(keyword in text.lower() for keyword in ["chest pain", "breathlessness", "fainting", "severe bleeding"]):
            alert_flag = "red"
        elif any(keyword in text.lower() for keyword in ["mild", "headache", "fatigue", "cough"]):
            alert_flag = "yellow"
        
        # Extract condition (simplified)
        condition = None
        if "if" in text.lower() and "children" in text.lower():
            if "1" in text:
                condition = "if_children=1"
            elif "2" in text:
                condition = "if_children=2"
        
        # Extract symptom type
        symptom = None
        if "chest" in text.lower():
            symptom = "chest_pain"
        elif "cough" in text.lower():
            symptom = "cough"
        elif "head" in text.lower():
            symptom = "headache"
        
        return ChromaQuestion(
            id=question_id,
            question_text=text,
            type=question_type,
            condition=condition,
            symptom=symptom,
            alert_flag=alert_flag
        )

    def create_embeddings(self, questions: List[ChromaQuestion]) -> List[List[float]]:
        """Create embeddings for questions using OpenAI"""
        embeddings = []
        
        for question in questions:
            response = openai.embeddings.create(
                model=settings.openai_embedding_model,
                input=question.question_text
            )
            embeddings.append(response.data[0].embedding)
        
        return embeddings

    def store_questions_in_chroma(self, questions: List[ChromaQuestion], embeddings: List[List[float]]):
        """Store questions and embeddings in Chroma DB"""
        ids = [q.id for q in questions]
        texts = [q.question_text for q in questions]
        metadatas = [
            {
                "type": q.type,
                "condition": q.condition or "none",
                "symptom": q.symptom or "none",
                "alert_flag": q.alert_flag
            }
            for q in questions
        ]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        print(f"Stored {len(questions)} questions in Chroma DB")

    def setup_chroma_db(self, pdf_path: str):
        """Complete setup process"""
        print("Parsing PDF questions...")
        questions = self.parse_pdf_questions(pdf_path)
        
        print("Creating embeddings...")
        embeddings = self.create_embeddings(questions)
        
        print("Storing in Chroma DB...")
        self.store_questions_in_chroma(questions, embeddings)
        
        print("Chroma DB setup complete!")
        return len(questions)

    def get_questions_by_type(self, question_type: str, condition: str = None) -> List[Dict[str, Any]]:
        """Retrieve questions by type and condition"""
        where_clause = {"type": question_type}
        if condition and condition != "none":
            where_clause["condition"] = condition
        
        # Use get method instead of query to avoid embedding function requirement
        results = self.collection.get(
            where=where_clause,
            limit=50
        )
        
        return [
            {
                "id": results["ids"][i],
                "question_text": results["documents"][i],
                "metadata": results["metadatas"][i]
            }
            for i in range(len(results["ids"]))
        ]

    def get_next_question(self, current_phase: str, completed_questions: List[str], 
                         patient_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get the next question based on current phase and patient data"""
        # Determine condition based on patient data
        condition = None
        if patient_data and "children" in patient_data:
            if patient_data["children"] == 1:
                condition = "if_children=1"
            elif patient_data["children"] == 2:
                condition = "if_children=2"
        
        # Get questions for current phase
        questions = self.get_questions_by_type(current_phase, condition)
        
        # Find next unanswered question
        for question in questions:
            if question["id"] not in completed_questions:
                return question
        
        return None

    def search_similar_questions(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for similar questions using semantic search"""
        # Create embedding for query
        response = openai.embeddings.create(
            model=settings.openai_embedding_model,
            input=query
        )
        query_embedding = response.data[0].embedding
        
        # Search in Chroma DB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        return [
            {
                "id": results["ids"][0][i],
                "question_text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            }
            for i in range(len(results["ids"][0]))
        ]


# Initialize Chroma DB setup
chroma_setup = ChromaDBSetup()
