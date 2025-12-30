"""
PLOS - Preprocessing & Explicit Extraction
Spell correction, time normalization, and rule-based extraction before AI.
Includes optional Gemini-enhanced preprocessing for messy inputs.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from shared.models import ExtractionType, FieldMetadata
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# SPELL CORRECTION
# ============================================================================

# Common misspellings in journal entries
SPELL_CORRECTIONS = {
    "alram": "alarm",
    "alrm": "alarm",
    "slept": "slept",
    "woke": "woke",
    "wokr": "work",
    "wrk": "work",
    "badmint": "badminton",
    "bminton": "badminton",
    "programing": "programming",
    "progamming": "programming",
    "conflic": "conflict",
    "conflct": "conflict",
    "exersice": "exercise",
    "excersize": "exercise",
    "breakfst": "breakfast",
    "brekfast": "breakfast",
}


def correct_spelling(text: str) -> str:
    """Apply spell corrections"""
    corrected = text
    for wrong, right in SPELL_CORRECTIONS.items():
        corrected = re.sub(r"\b" + wrong + r"\b", right, corrected, flags=re.IGNORECASE)
    return corrected


# ============================================================================
# TIME NORMALIZATION
# ============================================================================


def normalize_times(text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Normalize time mentions to standard format

    Examples:
    - "11 pm" -> "23:00"
    - "6:30 am" -> "06:30"
    - "midnight" -> "00:00"

    Returns:
    - normalized_text: Text with standardized times
    - time_mentions: Dict of detected times
    """
    time_mentions = {}

    # Pattern: "11 pm", "6:30am", "12:00 AM"
    pattern = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)"

    def replace_time(match):
        hour = int(match.group(1))
        minute = match.group(2) or "00"
        period = match.group(3).lower()

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        normalized = f"{hour:02d}:{minute}"

        # Store for extraction
        time_type = "unknown"
        if "wake" in text.lower() or "woke" in text.lower():
            time_type = "waketime"
        elif "sleep" in text.lower() or "bed" in text.lower():
            time_type = "bedtime"

        time_mentions[time_type] = normalized

        return normalized

    normalized_text = re.sub(pattern, replace_time, text)

    # Handle special cases
    normalized_text = normalized_text.replace("midnight", "00:00")
    normalized_text = normalized_text.replace("noon", "12:00")

    if "midnight" in text.lower():
        time_mentions["bedtime"] = "00:00"
    if "noon" in text.lower():
        time_mentions["waketime"] = "12:00"

    return normalized_text, time_mentions


# ============================================================================
# EXPLICIT EXTRACTION
# ============================================================================


class ExplicitExtractor:
    """
    Extract explicit data before AI processing

    Handles:
    - Sleep hours (from bedtime/waketime or direct mention)
    - Numbers and measurements
    - Activities mentioned
    - Mood indicators
    - Quantified metrics
    """

    def __init__(self):
        self.patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for extraction"""
        return {
            # Sleep patterns
            "sleep_hours": re.compile(
                r"(\d+\.?\d*)\s*(?:hours?|hrs?)\s*(?:of\s*)?sleep", re.IGNORECASE
            ),
            "sleep_direct": re.compile(
                r"slept\s*(?:for\s*)?(\d+\.?\d*)\s*(?:hours?|hrs?)", re.IGNORECASE
            ),
            # Exercise patterns
            "exercise_duration": re.compile(
                r"(\d+)\s*(?:min|minutes?)\s*(?:of\s*)?(\w+)", re.IGNORECASE
            ),
            "exercise_distance": re.compile(r"(\d+\.?\d*)\s*km\s*(\w+)", re.IGNORECASE),
            # Meal patterns
            "meals": re.compile(
                r"(?:ate|had|breakfast|lunch|dinner|snack).*?(?:eggs?|rice|chicken|dal|roti|bread)",
                re.IGNORECASE,
            ),
            # Water intake
            "water": re.compile(
                r"(\d+\.?\d*)\s*(?:liters?|L)\s*(?:of\s*)?water", re.IGNORECASE
            ),
            # Work hours
            "work_hours": re.compile(
                r"(?:worked|work)\s*(?:for\s*)?(\d+\.?\d*)\s*(?:hours?|hrs?)",
                re.IGNORECASE,
            ),
            # Activities
            "badminton": re.compile(r"\b(badminton|bmton|badmint)\b", re.IGNORECASE),
            "programming": re.compile(
                r"\b(programming|coding|code|dev|developer)\b", re.IGNORECASE
            ),
            "instagram": re.compile(r"\b(instagram|insta|ig)\b", re.IGNORECASE),
            # Mood indicators
            "positive_mood": re.compile(
                r"\b(happy|great|amazing|wonderful|excellent|good|energized|productive|focused)\b",
                re.IGNORECASE,
            ),
            "negative_mood": re.compile(
                r"\b(tired|exhausted|sad|angry|frustrated|stressed|anxious|bad|terrible)\b",
                re.IGNORECASE,
            ),
            # Conflict indicators
            "conflict": re.compile(
                r"\b(fight|conflict|argument|angry|mad|upset|jealous)\b", re.IGNORECASE
            ),
        }

    def extract(
        self, text: str, preprocessed_data: Dict[str, Any]
    ) -> Dict[str, FieldMetadata]:
        """
        Perform explicit extraction

        Returns:
        Dict of field_name -> FieldMetadata
        """
        extracted = {}

        # Extract sleep
        sleep_data = self._extract_sleep(
            text, preprocessed_data.get("time_mentions", {})
        )
        if sleep_data:
            extracted.update(sleep_data)

        # Extract exercise
        exercise_data = self._extract_exercise(text)
        if exercise_data:
            extracted.update(exercise_data)

        # Extract meals/nutrition
        nutrition_data = self._extract_nutrition(text)
        if nutrition_data:
            extracted.update(nutrition_data)

        # Extract work
        work_data = self._extract_work(text)
        if work_data:
            extracted.update(work_data)

        # Extract activities
        activities = self._extract_activities(text)
        if activities:
            extracted["activities"] = FieldMetadata(
                value=activities,
                type=ExtractionType.EXPLICIT,
                confidence=0.95,
                source="direct mention",
                reasoning="Activity keywords detected in text",
            )

        # Extract mood indicators
        mood_data = self._extract_mood_indicators(text)
        if mood_data:
            extracted.update(mood_data)

        # Extract conflict
        if self.patterns["conflict"].search(text):
            extracted["conflict_mentioned"] = FieldMetadata(
                value=True,
                type=ExtractionType.EXPLICIT,
                confidence=0.95,
                source="direct mention",
                user_said=self.patterns["conflict"].search(text).group(0),
                reasoning="Conflict keyword detected",
            )

        logger.info(f"Explicit extraction found {len(extracted)} fields")
        return extracted

    def _extract_sleep(
        self, text: str, time_mentions: Dict[str, str]
    ) -> Dict[str, FieldMetadata]:
        """Extract sleep data"""
        extracted = {}

        # Direct sleep hours mention
        match = self.patterns["sleep_hours"].search(text) or self.patterns[
            "sleep_direct"
        ].search(text)
        if match:
            hours = float(match.group(1))
            extracted["sleep_hours"] = FieldMetadata(
                value=hours,
                type=ExtractionType.EXPLICIT,
                confidence=0.97,
                source="direct mention",
                user_said=match.group(0),
                reasoning="Explicitly stated sleep duration",
            )
            return extracted

        # Calculate from bedtime and waketime
        if "bedtime" in time_mentions and "waketime" in time_mentions:
            bedtime_str = time_mentions["bedtime"]
            waketime_str = time_mentions["waketime"]

            try:
                bed_hour, bed_min = map(int, bedtime_str.split(":"))
                wake_hour, wake_min = map(int, waketime_str.split(":"))

                bed_minutes = bed_hour * 60 + bed_min
                wake_minutes = wake_hour * 60 + wake_min

                # Handle overnight sleep
                if wake_minutes <= bed_minutes:
                    wake_minutes += 24 * 60

                sleep_minutes = wake_minutes - bed_minutes
                sleep_hours = sleep_minutes / 60

                extracted["sleep_hours"] = FieldMetadata(
                    value=round(sleep_hours, 1),
                    type=ExtractionType.EXPLICIT,
                    confidence=0.95,
                    source="calculation",
                    reasoning=f"Calculated from bedtime {bedtime_str} and waketime {waketime_str}",
                )

                extracted["bedtime"] = FieldMetadata(
                    value=bedtime_str,
                    type=ExtractionType.EXPLICIT,
                    confidence=0.95,
                    source="direct mention",
                )

                extracted["waketime"] = FieldMetadata(
                    value=waketime_str,
                    type=ExtractionType.EXPLICIT,
                    confidence=0.95,
                    source="direct mention",
                )

            except Exception as e:
                logger.warning(f"Failed to calculate sleep hours: {e}")

        return extracted

    def _extract_exercise(self, text: str) -> Dict[str, FieldMetadata]:
        """Extract exercise data"""
        extracted = {}

        # Duration
        match = self.patterns["exercise_duration"].search(text)
        if match:
            duration = int(match.group(1))
            exercise_type = match.group(2).lower()

            extracted["exercise_duration_minutes"] = FieldMetadata(
                value=duration,
                type=ExtractionType.EXPLICIT,
                confidence=0.95,
                source="direct mention",
                user_said=match.group(0),
                reasoning="Explicitly stated exercise duration",
            )

            extracted["exercise_type"] = FieldMetadata(
                value=exercise_type,
                type=ExtractionType.EXPLICIT,
                confidence=0.90,
                source="direct mention",
                user_said=match.group(0),
            )

        # Distance
        match = self.patterns["exercise_distance"].search(text)
        if match:
            distance = float(match.group(1))
            exercise_type = match.group(2).lower()

            extracted["exercise_distance_km"] = FieldMetadata(
                value=distance,
                type=ExtractionType.EXPLICIT,
                confidence=0.95,
                source="direct mention",
                user_said=match.group(0),
            )

            if "exercise_type" not in extracted:
                extracted["exercise_type"] = FieldMetadata(
                    value=exercise_type,
                    type=ExtractionType.EXPLICIT,
                    confidence=0.90,
                    source="direct mention",
                )

        return extracted

    def _extract_nutrition(self, text: str) -> Dict[str, FieldMetadata]:
        """Extract nutrition data"""
        extracted = {}

        # Water intake
        match = self.patterns["water"].search(text)
        if match:
            liters = float(match.group(1))
            extracted["water_intake_liters"] = FieldMetadata(
                value=liters,
                type=ExtractionType.EXPLICIT,
                confidence=0.95,
                source="direct mention",
                user_said=match.group(0),
            )

        # Meal mentions
        meals = self.patterns["meals"].findall(text)
        if meals:
            extracted["meals_mentioned"] = FieldMetadata(
                value=len(meals),
                type=ExtractionType.EXPLICIT,
                confidence=0.80,
                source="direct mention",
                reasoning=f"Detected {len(meals)} meal mentions",
            )

        return extracted

    def _extract_work(self, text: str) -> Dict[str, FieldMetadata]:
        """Extract work data"""
        extracted = {}

        match = self.patterns["work_hours"].search(text)
        if match:
            hours = float(match.group(1))
            extracted["work_hours"] = FieldMetadata(
                value=hours,
                type=ExtractionType.EXPLICIT,
                confidence=0.90,
                source="direct mention",
                user_said=match.group(0),
            )

        return extracted

    def _extract_activities(self, text: str) -> List[str]:
        """Extract mentioned activities"""
        activities = []

        if self.patterns["badminton"].search(text):
            activities.append("badminton")
        if self.patterns["programming"].search(text):
            activities.append("programming")
        if self.patterns["instagram"].search(text):
            activities.append("instagram")

        return activities

    def _extract_mood_indicators(self, text: str) -> Dict[str, FieldMetadata]:
        """Extract mood indicators from keywords"""
        extracted = {}

        positive_matches = self.patterns["positive_mood"].findall(text)
        negative_matches = self.patterns["negative_mood"].findall(text)

        if positive_matches or negative_matches:
            # Estimate mood score from keyword sentiment
            positive_count = len(positive_matches)
            negative_count = len(negative_matches)

            if positive_count > negative_count:
                mood_score = 7.0 + min(positive_count, 3)
                confidence = 0.65
            elif negative_count > positive_count:
                mood_score = 5.0 - min(negative_count, 4)
                confidence = 0.65
            else:
                mood_score = 6.0
                confidence = 0.50

            extracted["mood_score_estimate"] = FieldMetadata(
                value=mood_score,
                type=ExtractionType.INFERRED,
                confidence=confidence,
                source="keyword_analysis",
                reasoning=f"Estimated from {positive_count} positive and {negative_count} negative keywords",
            )

        return extracted


# ============================================================================
# PREPROCESSING PIPELINE
# ============================================================================


class Preprocessor:
    """Complete preprocessing pipeline"""

    def __init__(self):
        self.explicit_extractor = ExplicitExtractor()

    def process(
        self, raw_text: str
    ) -> Tuple[str, Dict[str, Any], Dict[str, FieldMetadata]]:
        """
        Full preprocessing pipeline

        Returns:
        - preprocessed_text: Cleaned and normalized text
        - preprocessing_data: Metadata from preprocessing
        - explicit_extractions: Explicitly extracted fields
        """
        logger.info("Starting preprocessing pipeline")

        # Step 1: Spell correction
        corrected_text = correct_spelling(raw_text)

        # Step 2: Time normalization
        normalized_text, time_mentions = normalize_times(corrected_text)

        # Step 3: Explicit extraction
        preprocessing_data = {
            "original_text": raw_text,
            "spell_corrected": corrected_text != raw_text,
            "time_mentions": time_mentions,
        }

        explicit_extractions = self.explicit_extractor.extract(
            normalized_text, preprocessing_data
        )

        logger.info(
            f"Preprocessing complete. Extracted {len(explicit_extractions)} explicit fields"
        )

        return normalized_text, preprocessing_data, explicit_extractions

    async def process_with_gemini(
        self,
        raw_text: str,
        gemini_client: Optional[Any] = None,
    ) -> Tuple[str, Dict[str, Any], Dict[str, FieldMetadata]]:
        """
        Enhanced preprocessing using Gemini for messy/shorthand text.

        Use this when the journal entry contains:
        - Heavy abbreviations ("wrked frm hm", "bfast @ 9")
        - Voice-to-text errors
        - Mixed languages
        - Very informal writing

        Args:
            raw_text: Raw journal entry
            gemini_client: ResilientGeminiClient instance

        Returns:
            Same as process() - (preprocessed_text, preprocessing_data, explicit_extractions)
        """
        if not gemini_client:
            logger.warning(
                "No Gemini client provided, falling back to rule-based preprocessing"
            )
            return self.process(raw_text)

        logger.info("Starting Gemini-enhanced preprocessing")

        try:
            # Use Gemini to clean and expand the text
            cleaned_text = await self._gemini_clean_text(raw_text, gemini_client)

            # Then apply standard pipeline on cleaned text
            corrected_text = correct_spelling(cleaned_text)
            normalized_text, time_mentions = normalize_times(corrected_text)

            preprocessing_data = {
                "original_text": raw_text,
                "gemini_cleaned": cleaned_text,
                "spell_corrected": corrected_text != cleaned_text,
                "time_mentions": time_mentions,
                "used_gemini_preprocessing": True,
            }

            explicit_extractions = self.explicit_extractor.extract(
                normalized_text, preprocessing_data
            )

            logger.info(
                f"Gemini preprocessing complete. Extracted {len(explicit_extractions)} explicit fields"
            )

            return normalized_text, preprocessing_data, explicit_extractions

        except Exception as e:
            logger.error(
                f"Gemini preprocessing failed: {e}, falling back to rule-based"
            )
            return self.process(raw_text)

    async def _gemini_clean_text(self, raw_text: str, gemini_client: Any) -> str:
        """
        Use Gemini to clean and expand shorthand/messy text.

        This is a lightweight call focused only on text cleanup, not extraction.
        """
        prompt = f"""Clean and expand this journal entry text. Fix:
1. Spelling errors and typos
2. Abbreviations (expand them: "bfast" -> "breakfast", "wrk" -> "work")
3. Missing punctuation
4. Voice-to-text errors

Keep the meaning exactly the same. Do NOT add new information.
Do NOT extract data - just clean the text.

Original:
\"\"\"{raw_text}\"\"\"

Cleaned text (return ONLY the cleaned text, no explanation):"""

        try:
            response = await gemini_client.generate_content(
                prompt=prompt,
                model="gemini-2.5-flash",
            )

            cleaned = response.strip()

            # Basic validation - shouldn't be drastically different length
            if len(cleaned) < len(raw_text) * 0.5 or len(cleaned) > len(raw_text) * 3:
                logger.warning(
                    "Gemini cleaning produced suspicious output, using original"
                )
                return raw_text

            logger.debug(f"Text cleaned: {len(raw_text)} -> {len(cleaned)} chars")
            return cleaned

        except Exception as e:
            logger.error(f"Gemini text cleaning failed: {e}")
            return raw_text
