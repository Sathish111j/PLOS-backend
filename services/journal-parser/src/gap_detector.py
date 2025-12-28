"""
Gap Detector - Identifies missing information in journal entries using Gemini

Uses Gemini's reasoning capabilities to detect what metrics are missing
and should be tracked for complete health/productivity insights
"""

from typing import List
from google import genai
from google.genai.types import GenerateContentConfig

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class GapDetector:
    """
    Detects missing metrics and information in journal entries
    
    Uses Gemini to analyze what health/productivity data is absent
    """
    
    EXPECTED_METRICS = [
        "mood_score",
        "energy_level",
        "sleep_hours",
        "exercise_minutes",
        "water_intake",
        "meals_count",
        "work_hours",
        "productivity_score",
        "meditation_minutes",
        "social_interaction"
    ]
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """
        Initialize gap detector
        
        Args:
            api_key: Gemini API key
            model: Gemini model to use
        """
        self.api_key = api_key
        self.model_name = model
        self.client = genai.Client(api_key=api_key)
        
        logger.info(f"Initialized GapDetector with model: {model}")
    
    async def detect_gaps(self, entry_text: str) -> List[str]:
        """
        Detect missing metrics in a journal entry
        
        Args:
            entry_text: Journal entry text
        
        Returns:
            List of missing metric names
        """
        try:
            logger.info(f"Detecting gaps in entry (length: {len(entry_text)})")
            
            # Create prompt for gap detection
            prompt = f"""Analyze this journal entry and identify what important health and productivity metrics are MISSING.

Journal entry:
{entry_text}

Expected metrics to check for:
- Mood/emotions (mood_score, energy_level, stress_level)
- Sleep (sleep_hours, sleep_quality)
- Exercise (exercise_minutes, exercise_type)
- Nutrition (water_intake, meals_count, diet_quality)
- Work/Productivity (work_hours, productivity_score, focus_level)
- Habits (meditation_minutes, reading_minutes, social_interaction)

Task: Return ONLY a JSON array of missing metric names. Example: ["sleep_hours", "exercise_minutes", "water_intake"]

Rules:
- Only list metrics that are COMPLETELY ABSENT from the entry
- If a metric is mentioned (even vaguely), don't include it
- Return an empty array [] if all major categories are covered
- Use the exact metric names from the list above"""

            # Generate response
            config = GenerateContentConfig(
                temperature=0.2,  # Low temperature for consistent analysis
                response_mime_type="application/json"
            )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            # Parse response
            import json
            missing_metrics = json.loads(response.text)
            
            if not isinstance(missing_metrics, list):
                logger.warning(f"Unexpected gap detection response: {response.text}")
                return []
            
            logger.info(f"Detected {len(missing_metrics)} missing metrics: {missing_metrics}")
            
            return missing_metrics
            
        except Exception as e:
            logger.error(f"Error detecting gaps: {str(e)}")
            return []  # Return empty list on error
    
    async def generate_followup_questions(self, missing_metrics: List[str]) -> List[str]:
        """
        Generate follow-up questions based on missing metrics
        
        Args:
            missing_metrics: List of missing metric names
        
        Returns:
            List of suggested follow-up questions
        """
        if not missing_metrics:
            return []
        
        try:
            prompt = f"""Based on these missing metrics from a journal entry, generate 2-3 gentle follow-up questions to help the user track their health and productivity better.

Missing metrics: {', '.join(missing_metrics)}

Guidelines:
- Questions should be friendly and conversational
- Don't ask about all missing metrics - prioritize the most important ones
- Keep questions brief and specific
- Frame questions positively (not judgmental)

Return as JSON array of strings. Example: ["How many hours did you sleep last night?", "Did you get any exercise today?"]"""

            config = GenerateContentConfig(
                temperature=0.7,  # Higher temperature for more natural questions
                response_mime_type="application/json"
            )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            import json
            questions = json.loads(response.text)
            
            logger.info(f"Generated {len(questions)} follow-up questions")
            return questions
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return []
    
    def calculate_completeness_score(self, missing_metrics: List[str]) -> float:
        """
        Calculate completeness score based on missing metrics
        
        Args:
            missing_metrics: List of missing metric names
        
        Returns:
            Completeness score (0.0 to 1.0)
        """
        total_metrics = len(self.EXPECTED_METRICS)
        missing_count = len(missing_metrics)
        
        score = max(0.0, 1.0 - (missing_count / total_metrics))
        
        logger.debug(f"Completeness score: {score:.2f} ({missing_count}/{total_metrics} missing)")
        
        return score
