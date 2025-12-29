"""
PLOS v2.0 - Quality Scoring System
Comprehensive quality assessment matching architecture specification
"""

from typing import Any, Dict, List
from shared.models import ExtractionType, FieldMetadata, QualityLevel
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# QUALITY SCORING (ARCHITECTURE-COMPLIANT)
# ============================================================================

class QualityScorer:
    """
    Calculate quality score per architecture specification:
    
    Base: 1.0
    - Per explicit field: 0 (perfect)
    - Per inferred field: -0.05
    - Per missing field: -0.03 to -0.10 (importance-weighted)
    - If any inference_confidence < 0.50: -0.10
    - If consistency check fails: -0.15
    - If health alert triggered: -0.10
    - If temporal inconsistency: -0.05
    
    Quality Levels:
    - 0.90+: EXCELLENT (trust for important decisions)
    - 0.80-0.89: VERY_GOOD (good for analysis)
    - 0.70-0.79: GOOD (acceptable for patterns)
    - 0.60-0.69: ACCEPTABLE (use with caution)
    - 0.50-0.59: POOR (informational only)
    - <0.50: UNRELIABLE (flag for clarification)
    """
    
    # Field importance weights (0.0-1.0)
    # Higher weight = more penalty if missing
    FIELD_IMPORTANCE = {
        # Critical fields (0.10 penalty if missing)
        "sleep_hours": 0.10,
        "mood_score": 0.10,
        "energy_level": 0.10,
        
        # Important fields (0.07 penalty if missing)
        "stress_level": 0.07,
        "sleep_quality": 0.07,
        
        # Moderate fields (0.05 penalty if missing)
        "productivity": 0.05,
        "work_hours": 0.05,
        "exercise": 0.05,
        
        # Optional fields (0.03 penalty if missing)
        "nutrition": 0.03,
        "social_interaction": 0.03,
        "gratitude": 0.03,
        "challenges": 0.03,
        "goals": 0.03,
        "relationship_quality": 0.03,
    }
    
    # Expected fields for complete extraction
    ALL_FIELDS = set(FIELD_IMPORTANCE.keys())
    
    def calculate_quality(
        self,
        extracted_data: Dict[str, FieldMetadata],
        anomalies_detected: List[str],
        health_alerts: List[str],
        consistency_issues: List[str]
    ) -> tuple[float, QualityLevel, Dict[str, Any]]:
        """
        Calculate comprehensive quality score
        
        Returns:
            (score, level, breakdown)
        """
        score = 1.0  # Start at perfect
        breakdown = {
            "base": 1.0,
            "explicit_fields": 0,
            "inferred_fields": 0,
            "missing_fields": 0,
            "low_confidence_penalty": 0,
            "consistency_penalty": 0,
            "health_alert_penalty": 0,
            "temporal_penalty": 0
        }
        
        # Count extraction types
        explicit_count = 0
        inferred_count = 0
        low_confidence_count = 0
        
        for field_name, field_data in extracted_data.items():
            if field_data.type == ExtractionType.EXPLICIT:
                explicit_count += 1
            elif field_data.type in [ExtractionType.INFERRED, ExtractionType.ESTIMATED]:
                inferred_count += 1
                score -= 0.05
                breakdown["inferred_fields"] -= 0.05
            
            # Check confidence
            if field_data.confidence < 0.50:
                low_confidence_count += 1
        
        # Missing field penalties (importance-weighted)
        missing_fields = self.ALL_FIELDS - set(extracted_data.keys())
        for field in missing_fields:
            penalty = self.FIELD_IMPORTANCE.get(field, 0.03)
            score -= penalty
            breakdown["missing_fields"] -= penalty
        
        # Low confidence penalty
        if low_confidence_count > 0:
            score -= 0.10
            breakdown["low_confidence_penalty"] = -0.10
        
        # Consistency check penalty
        if consistency_issues:
            score -= 0.15
            breakdown["consistency_penalty"] = -0.15
        
        # Health alert penalty (indicates unusual/concerning data)
        if health_alerts:
            score -= 0.10
            breakdown["health_alert_penalty"] = -0.10
        
        # Temporal inconsistency penalty
        temporal_issues = [a for a in anomalies_detected if "temporal" in a.lower()]
        if temporal_issues:
            score -= 0.05
            breakdown["temporal_penalty"] = -0.05
        
        # Ensure score in valid range
        score = max(0.0, min(1.0, score))
        
        # Determine quality level
        level = self._score_to_level(score)
        
        logger.debug(f"Quality score: {score:.2f} ({level}), breakdown: {breakdown}")
        
        return score, level, breakdown
    
    def _score_to_level(self, score: float) -> QualityLevel:
        """Convert score to quality level"""
        if score >= 0.90:
            return QualityLevel.EXCELLENT
        elif score >= 0.80:
            return QualityLevel.VERY_GOOD
        elif score >= 0.70:
            return QualityLevel.GOOD
        elif score >= 0.60:
            return QualityLevel.ACCEPTABLE
        elif score >= 0.50:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNRELIABLE
    
    def should_request_clarification(
        self,
        score: float,
        level: QualityLevel,
        missing_fields: List[str]
    ) -> tuple[bool, List[str]]:
        """
        Determine if clarification should be requested
        
        Returns:
            (should_request, questions)
        """
        if score >= 0.60:
            return False, []
        
        questions = []
        
        # Generate clarification questions for critical missing fields
        critical_missing = [
            f for f in missing_fields
            if self.FIELD_IMPORTANCE.get(f, 0) >= 0.07
        ]
        
        for field in critical_missing:
            questions.append(self._generate_question(field))
        
        return True, questions
    
    def _generate_question(self, field_name: str) -> str:
        """Generate clarification question for missing field"""
        questions_map = {
            "sleep_hours": "How many hours did you sleep?",
            "sleep_quality": "How would you rate your sleep quality (1-10)?",
            "mood_score": "How was your mood today (1-10)?",
            "energy_level": "How was your energy level (1-10)?",
            "stress_level": "How stressed did you feel (1-10)?",
            "productivity": "How productive were you today (1-10)?",
            "work_hours": "How many hours did you work?",
            "exercise": "Did you exercise today? For how long?",
            "nutrition": "What did you eat today?",
            "social_interaction": "How was your social interaction quality (1-10)?",
        }
        
        return questions_map.get(
            field_name,
            f"Can you provide more details about {field_name.replace('_', ' ')}?"
        )


# ============================================================================
# CONSISTENCY CHECKER
# ============================================================================

class ConsistencyChecker:
    """
    Check for logical consistency in extracted data
    Per architecture: -0.15 penalty if consistency fails
    """
    
    def check_consistency(
        self,
        extracted_data: Dict[str, FieldMetadata]
    ) -> tuple[bool, List[str]]:
        """
        Check for inconsistencies
        
        Returns:
            (is_consistent, issues)
        """
        issues = []
        
        # Check 1: Sleep hours consistency
        if "sleep_hours" in extracted_data and "bedtime" in extracted_data and "waketime" in extracted_data:
            calculated_sleep = self._calculate_sleep_hours(
                extracted_data["bedtime"].value,
                extracted_data["waketime"].value
            )
            reported_sleep = extracted_data["sleep_hours"].value
            
            if abs(calculated_sleep - reported_sleep) > 1.5:
                issues.append(
                    f"Sleep hours mismatch: calculated {calculated_sleep:.1f}h vs reported {reported_sleep:.1f}h"
                )
        
        # Check 2: Mood-activity alignment
        if "mood_score" in extracted_data and "activities" in extracted_data:
            mood = extracted_data["mood_score"].value
            activities = extracted_data["activities"].value
            
            # High mood but negative activities?
            if mood >= 8 and any(neg in str(activities).lower() for neg in ["conflict", "fight", "argument"]):
                issues.append("High mood inconsistent with conflict activities")
        
        # Check 3: Energy-sleep alignment
        if "energy_level" in extracted_data and "sleep_hours" in extracted_data:
            energy = extracted_data["energy_level"].value
            sleep = extracted_data["sleep_hours"].value
            
            # Very low energy but good sleep?
            if energy <= 3 and sleep >= 8:
                issues.append("Low energy despite adequate sleep")
            
            # High energy but very poor sleep?
            elif energy >= 8 and sleep <= 4:
                issues.append("High energy despite poor sleep")
        
        # Check 4: Temporal consistency
        if "work_hours" in extracted_data:
            work_hours = extracted_data["work_hours"].value
            if work_hours > 24:
                issues.append(f"Work hours ({work_hours}h) exceeds 24 hours")
        
        is_consistent = len(issues) == 0
        
        if issues:
            logger.warning(f"Consistency issues detected: {issues}")
        
        return is_consistent, issues
    
    def _calculate_sleep_hours(self, bedtime: str, waketime: str) -> float:
        """Calculate sleep hours from times"""
        # Simplified - would use actual time parsing in production
        try:
            bed_hour = int(bedtime.split(":")[0])
            wake_hour = int(waketime.split(":")[0])
            
            if bed_hour > wake_hour:
                return (24 - bed_hour) + wake_hour
            else:
                return wake_hour - bed_hour
        except:
            return 0.0


# ============================================================================
# QUALITY METRICS
# ============================================================================

class QualityMetrics:
    """Track quality metrics across extractions"""
    
    def __init__(self):
        self.scores = []
        self.levels = []
    
    def add_extraction(self, score: float, level: QualityLevel):
        """Add extraction result"""
        self.scores.append(score)
        self.levels.append(level)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get quality statistics"""
        if not self.scores:
            return {"message": "No data"}
        
        return {
            "avg_score": sum(self.scores) / len(self.scores),
            "min_score": min(self.scores),
            "max_score": max(self.scores),
            "excellent_rate": f"{(self.levels.count(QualityLevel.EXCELLENT) / len(self.levels) * 100):.1f}%",
            "unreliable_rate": f"{(self.levels.count(QualityLevel.UNRELIABLE) / len(self.levels) * 100):.1f}%",
            "total_extractions": len(self.scores)
        }
