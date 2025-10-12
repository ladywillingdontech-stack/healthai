"""
Reports Service for Health AI Bot
Generates various reports for admins and doctors
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.firestore_service import firestore_service
from app.models import UserRole, AlertLevel

class ReportsService:
    def __init__(self):
        self.firestore = firestore_service
    
    async def get_patient_summary_report(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """Get patient summary report"""
        try:
            # Get all patients
            patients = await self.firestore.get_all_patients()
            
            # Filter by date range if provided
            if start_date and end_date:
                filtered_patients = []
                for patient in patients:
                    if start_date <= patient.get('created_at', datetime.now()) <= end_date:
                        filtered_patients.append(patient)
                patients = filtered_patients
            
            # Calculate statistics
            total_patients = len(patients)
            active_patients = len([p for p in patients if p.get('status') == 'active'])
            completed_patients = len([p for p in patients if p.get('status') == 'completed'])
            
            # Age distribution
            age_groups = {
                '0-18': 0,
                '19-35': 0,
                '36-50': 0,
                '51-65': 0,
                '65+': 0
            }
            
            for patient in patients:
                age = patient.get('age', 0)
                if age <= 18:
                    age_groups['0-18'] += 1
                elif age <= 35:
                    age_groups['19-35'] += 1
                elif age <= 50:
                    age_groups['36-50'] += 1
                elif age <= 65:
                    age_groups['51-65'] += 1
                else:
                    age_groups['65+'] += 1
            
            return {
                'total_patients': total_patients,
                'active_patients': active_patients,
                'completed_patients': completed_patients,
                'age_distribution': age_groups,
                'report_date': datetime.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            print(f"❌ Error generating patient summary report: {e}")
            return {}
    
    async def get_emr_summary_report(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """Get EMR summary report"""
        try:
            # Get all EMRs
            emrs = await self.firestore.get_all_emrs()
            
            # Filter by date range if provided
            if start_date and end_date:
                filtered_emrs = []
                for emr in emrs:
                    if start_date <= emr.get('created_at', datetime.now()) <= end_date:
                        filtered_emrs.append(emr)
                emrs = filtered_emrs
            
            # Calculate statistics
            total_emrs = len(emrs)
            red_alerts = len([e for e in emrs if e.get('alert_level') == AlertLevel.RED])
            yellow_alerts = len([e for e in emrs if e.get('alert_level') == AlertLevel.YELLOW])
            normal_cases = len([e for e in emrs if e.get('alert_level') == AlertLevel.NONE])
            
            # Common diagnoses
            diagnoses = {}
            for emr in emrs:
                diagnosis = emr.get('diagnosis', 'Unknown')
                diagnoses[diagnosis] = diagnoses.get(diagnosis, 0) + 1
            
            # Sort by frequency
            common_diagnoses = sorted(diagnoses.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'total_emrs': total_emrs,
                'red_alerts': red_alerts,
                'yellow_alerts': yellow_alerts,
                'normal_cases': normal_cases,
                'common_diagnoses': common_diagnoses,
                'report_date': datetime.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            print(f"❌ Error generating EMR summary report: {e}")
            return {}
    
    async def get_conversation_analytics_report(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """Get conversation analytics report"""
        try:
            # Get all conversations
            conversations = await self.firestore.get_all_conversations()
            
            # Filter by date range if provided
            if start_date and end_date:
                filtered_conversations = []
                for conv in conversations:
                    if start_date <= conv.get('created_at', datetime.now()) <= end_date:
                        filtered_conversations.append(conv)
                conversations = filtered_conversations
            
            # Calculate statistics
            total_conversations = len(conversations)
            completed_conversations = len([c for c in conversations if c.get('status') == 'completed'])
            ongoing_conversations = len([c for c in conversations if c.get('status') == 'ongoing'])
            
            # Average conversation duration
            durations = []
            for conv in conversations:
                if conv.get('completed_at') and conv.get('created_at'):
                    duration = conv['completed_at'] - conv['created_at']
                    durations.append(duration.total_seconds() / 60)  # Convert to minutes
            
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Phase completion rates
            phase_stats = {
                'onboarding': 0,
                'demographic': 0,
                'symptom': 0,
                'wrap_up': 0,
                'completed': 0
            }
            
            for conv in conversations:
                phase = conv.get('current_phase', 'onboarding')
                phase_stats[phase] = phase_stats.get(phase, 0) + 1
            
            return {
                'total_conversations': total_conversations,
                'completed_conversations': completed_conversations,
                'ongoing_conversations': ongoing_conversations,
                'completion_rate': (completed_conversations / total_conversations * 100) if total_conversations > 0 else 0,
                'average_duration_minutes': round(avg_duration, 2),
                'phase_distribution': phase_stats,
                'report_date': datetime.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            print(f"❌ Error generating conversation analytics report: {e}")
            return {}
    
    async def get_alert_summary_report(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """Get alert summary report"""
        try:
            # Get all EMRs with alerts
            emrs = await self.firestore.get_all_emrs()
            
            # Filter by date range if provided
            if start_date and end_date:
                filtered_emrs = []
                for emr in emrs:
                    if start_date <= emr.get('created_at', datetime.now()) <= end_date:
                        filtered_emrs.append(emr)
                emrs = filtered_emrs
            
            # Count alerts by level
            alert_counts = {
                'red': 0,
                'yellow': 0,
                'none': 0
            }
            
            red_alerts = []
            yellow_alerts = []
            
            for emr in emrs:
                alert_level = emr.get('alert_level', AlertLevel.NONE)
                if alert_level == AlertLevel.RED:
                    alert_counts['red'] += 1
                    red_alerts.append(emr)
                elif alert_level == AlertLevel.YELLOW:
                    alert_counts['yellow'] += 1
                    yellow_alerts.append(emr)
                else:
                    alert_counts['none'] += 1
            
            # Common red alert reasons
            red_reasons = {}
            for emr in red_alerts:
                reason = emr.get('alert_reason', 'Unknown')
                red_reasons[reason] = red_reasons.get(reason, 0) + 1
            
            # Common yellow alert reasons
            yellow_reasons = {}
            for emr in yellow_alerts:
                reason = emr.get('alert_reason', 'Unknown')
                yellow_reasons[reason] = yellow_reasons.get(reason, 0) + 1
            
            return {
                'total_alerts': alert_counts['red'] + alert_counts['yellow'],
                'red_alerts': alert_counts['red'],
                'yellow_alerts': alert_counts['yellow'],
                'normal_cases': alert_counts['none'],
                'red_alert_reasons': sorted(red_reasons.items(), key=lambda x: x[1], reverse=True),
                'yellow_alert_reasons': sorted(yellow_reasons.items(), key=lambda x: x[1], reverse=True),
                'report_date': datetime.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            print(f"❌ Error generating alert summary report: {e}")
            return {}
    
    async def get_daily_summary_report(self, date: datetime = None) -> Dict[str, Any]:
        """Get daily summary report"""
        if not date:
            date = datetime.now()
        
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Get all reports for the day
        patient_report = await self.get_patient_summary_report(start_date, end_date)
        emr_report = await self.get_emr_summary_report(start_date, end_date)
        conversation_report = await self.get_conversation_analytics_report(start_date, end_date)
        alert_report = await self.get_alert_summary_report(start_date, end_date)
        
        return {
            'date': date.isoformat(),
            'patient_summary': patient_report,
            'emr_summary': emr_report,
            'conversation_analytics': conversation_report,
            'alert_summary': alert_report
        }
    
    async def get_user_activity_report(self, user_id: str, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """Get user activity report"""
        try:
            # Get user's EMRs
            user_emrs = await self.firestore.get_emrs_by_doctor(user_id)
            
            # Filter by date range if provided
            if start_date and end_date:
                filtered_emrs = []
                for emr in user_emrs:
                    if start_date <= emr.get('created_at', datetime.now()) <= end_date:
                        filtered_emrs.append(emr)
                user_emrs = filtered_emrs
            
            # Calculate statistics
            total_emrs = len(user_emrs)
            red_alerts = len([e for e in user_emrs if e.get('alert_level') == AlertLevel.RED])
            yellow_alerts = len([e for e in user_emrs if e.get('alert_level') == AlertLevel.YELLOW])
            
            # Most common diagnoses
            diagnoses = {}
            for emr in user_emrs:
                diagnosis = emr.get('diagnosis', 'Unknown')
                diagnoses[diagnosis] = diagnoses.get(diagnosis, 0) + 1
            
            common_diagnoses = sorted(diagnoses.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                'user_id': user_id,
                'total_emrs': total_emrs,
                'red_alerts': red_alerts,
                'yellow_alerts': yellow_alerts,
                'common_diagnoses': common_diagnoses,
                'report_date': datetime.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            print(f"❌ Error generating user activity report: {e}")
            return {}

# Global instance
reports_service = ReportsService()






