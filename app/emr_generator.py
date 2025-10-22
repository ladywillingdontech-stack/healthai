import firebase_admin
from firebase_admin import credentials, storage
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import settings
from app.models import EMRCreate, EMR


class EMRGenerator:
    def __init__(self):
        # Initialize Firebase
        if not firebase_admin._apps:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "private_key_id": settings.firebase_private_key_id,
                "private_key": settings.firebase_private_key,
                "client_email": settings.firebase_client_email,
                "client_id": settings.firebase_client_id,
                "auth_uri": settings.firebase_auth_uri,
                "token_uri": settings.firebase_token_uri,
                "auth_provider_x509_cert_url": settings.firebase_auth_provider_x509_cert_url,
                "client_x509_cert_url": settings.firebase_client_x509_cert_url
            })
            firebase_admin.initialize_app(cred, {
                'storageBucket': f"{settings.firebase_project_id}.appspot.com"
            })
        
        self.bucket = storage.bucket()

    def generate_pdf(self, emr_data: EMRCreate, patient_data: Dict[str, Any]) -> str:
        """Generate PDF EMR document"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            # Create PDF document
            doc = SimpleDocTemplate(temp_file_path, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.darkblue
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.darkblue
            )
            
            normal_style = styles['Normal']
            normal_style.fontSize = 10
            
            # Build content
            content = []
            
            # Header
            content.append(Paragraph("Health AI Bot - Electronic Medical Record", title_style))
            content.append(Spacer(1, 20))
            
            # Patient Information
            content.append(Paragraph("Patient Information", heading_style))
            patient_info = [
                ["Patient ID:", str(emr_data.patient_id)],
                ["Session ID:", emr_data.session_id],
                ["Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ["Phone:", patient_data.get("phone_number", "N/A")]
            ]
            
            patient_table = Table(patient_info, colWidths=[2*inch, 4*inch])
            patient_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            content.append(patient_table)
            content.append(Spacer(1, 20))
            
            # Demographics
            if emr_data.demographics:
                content.append(Paragraph("Demographics", heading_style))
                demo_data = []
                for key, value in emr_data.demographics.dict().items():
                    if value is not None:
                        demo_data.append([key.replace('_', ' ').title(), str(value)])
                
                if demo_data:
                    demo_table = Table(demo_data, colWidths=[2*inch, 4*inch])
                    demo_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    content.append(demo_table)
                    content.append(Spacer(1, 20))
            
            # Onboarding Information
            if emr_data.onboarding:
                content.append(Paragraph("Medical History", heading_style))
                onboard_data = []
                for key, value in emr_data.onboarding.dict().items():
                    if value is not None:
                        onboard_data.append([key.replace('_', ' ').title(), str(value)])
                
                if onboard_data:
                    onboard_table = Table(onboard_data, colWidths=[2*inch, 4*inch])
                    onboard_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    content.append(onboard_table)
                    content.append(Spacer(1, 20))
            
            # Symptoms
            if emr_data.symptoms:
                content.append(Paragraph("Symptoms", heading_style))
                symptom_data = [["Symptom", "Duration", "Severity", "Details"]]
                for symptom in emr_data.symptoms:
                    symptom_data.append([
                        symptom.symptom,
                        symptom.duration or "N/A",
                        symptom.severity or "N/A",
                        symptom.details or "N/A"
                    ])
                
                symptom_table = Table(symptom_data, colWidths=[1.5*inch, 1*inch, 1*inch, 2.5*inch])
                symptom_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                content.append(symptom_table)
                content.append(Spacer(1, 20))
            
            # Alerts
            if emr_data.alerts and emr_data.alerts.status != "none":
                alert_color = colors.red if emr_data.alerts.status == "red" else colors.orange
                content.append(Paragraph(f"⚠️ ALERT: {emr_data.alerts.status.upper()}", 
                                       ParagraphStyle('Alert', parent=styles['Heading2'], 
                                                    fontSize=14, textColor=alert_color)))
                content.append(Paragraph(f"Reason: {emr_data.alerts.reason}", normal_style))
                content.append(Spacer(1, 20))
            
            # AI Summary
            if emr_data.ai_summary:
                content.append(Paragraph("AI Clinical Summary", heading_style))
                content.append(Paragraph(emr_data.ai_summary, normal_style))
                content.append(Spacer(1, 20))
            
            # Dynamic Notes
            if emr_data.dynamic_notes:
                content.append(Paragraph("Additional Notes", heading_style))
                for note in emr_data.dynamic_notes:
                    content.append(Paragraph(f"• {note}", normal_style))
                content.append(Spacer(1, 20))
            
            # Footer
            content.append(Spacer(1, 30))
            content.append(Paragraph("Generated by Health AI Bot", 
                                   ParagraphStyle('Footer', parent=styles['Normal'], 
                                                fontSize=8, alignment=TA_CENTER)))
            
            # Build PDF
            doc.build(content)
            
            return temp_file_path
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return None

    def upload_to_firebase(self, file_path: str, filename: str) -> Optional[str]:
        """Upload PDF to Firebase Storage"""
        try:
            blob = self.bucket.blob(f"emrs/{filename}")
            blob.upload_from_filename(file_path)
            
            # Make the file publicly accessible
            blob.make_public()
            
            return blob.public_url
            
        except Exception as e:
            print(f"Error uploading to Firebase: {e}")
            return None

    def generate_and_upload_emr(self, emr_data: EMRCreate, patient_data: Dict[str, Any]) -> Optional[str]:
        """Complete EMR generation and upload process"""
        try:
            # Generate PDF
            pdf_path = self.generate_pdf(emr_data, patient_data)
            if not pdf_path:
                return None
            
            # Create filename
            filename = f"emr_{emr_data.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Upload to Firebase
            pdf_url = self.upload_to_firebase(pdf_path, filename)
            
            # Clean up temporary file
            os.unlink(pdf_path)
            
            return pdf_url
            
        except Exception as e:
            print(f"Error in complete EMR generation: {e}")
            return None

    def create_emr_json(self, emr_data: EMRCreate) -> Dict[str, Any]:
        """Create structured JSON for EMR storage"""
        return {
            "patient_id": str(emr_data.patient_id),
            "session_id": emr_data.session_id,
            "demographics": emr_data.demographics.dict(),
            "onboarding": emr_data.onboarding.dict(),
            "symptoms": [symptom.dict() for symptom in emr_data.symptoms],
            "dynamic_notes": emr_data.dynamic_notes,
            "alerts": emr_data.alerts.dict(),
            "ai_summary": emr_data.ai_summary,
            "pdf_url": emr_data.pdf_url,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }


# Initialize EMR generator
emr_generator = EMRGenerator()
