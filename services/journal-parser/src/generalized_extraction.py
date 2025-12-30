"""
PLOS - Generalized Extraction System
Handles infinite variety of user data with controlled vocabulary and gap detection.
Normalizes field names, tracks time of day, and asks clarification questions.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from shared.gemini.client import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================


class TimeOfDay(Enum):
    """Time of day classification for activities and events."""

    EARLY_MORNING = "early_morning"  # 4am - 7am
    MORNING = "morning"  # 7am - 12pm
    AFTERNOON = "afternoon"  # 12pm - 5pm
    EVENING = "evening"  # 5pm - 9pm
    NIGHT = "night"  # 9pm - 12am
    LATE_NIGHT = "late_night"  # 12am - 4am


class GapPriority(Enum):
    """Priority levels for data gaps requiring clarification."""

    HIGH = 1  # Missing core data (sleep hours, main activity type)
    MEDIUM = 2  # Missing details (duration, intensity)
    LOW = 3  # Nice to have (satisfaction, notes)


@dataclass
class DataGap:
    """Represents missing information that needs user clarification."""

    field_category: str  # 'activity', 'meal', 'sleep', 'social'
    question: str  # "What sport did you play?"
    context: str  # "You mentioned 'played well'"
    original_mention: str  # The exact ambiguous text
    priority: GapPriority = GapPriority.MEDIUM
    suggested_options: List[str] = field(default_factory=list)


@dataclass
class NormalizedActivity:
    """Normalized activity with canonical name from controlled vocabulary."""

    canonical_name: Optional[str]  # From controlled vocabulary (None if unknown)
    raw_name: str  # Original user text
    category: str  # physical, mental, leisure, etc.
    duration_minutes: Optional[int] = None
    time_of_day: Optional[TimeOfDay] = None
    start_time: Optional[str] = None  # HH:MM
    end_time: Optional[str] = None  # HH:MM
    intensity: Optional[str] = None  # low, medium, high
    satisfaction: Optional[int] = None  # 1-10
    calories_burned: Optional[int] = None
    is_screen_time: bool = False
    confidence: float = 0.5
    needs_clarification: bool = False
    raw_mention: Optional[str] = None


@dataclass
class NormalizedConsumption:
    """Normalized food/drink with canonical name."""

    canonical_name: Optional[str]
    raw_name: str
    consumption_type: str  # meal, snack, drink, medication
    meal_type: Optional[str] = None  # breakfast, lunch, dinner, snack
    time_of_day: Optional[TimeOfDay] = None
    consumption_time: Optional[str] = None  # HH:MM
    quantity: float = 1.0
    unit: str = "serving"
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    is_healthy: Optional[bool] = None
    is_home_cooked: Optional[bool] = None
    confidence: float = 0.5
    raw_mention: Optional[str] = None


@dataclass
class ExtractionResult:
    """Complete extraction result with gaps for clarification."""

    # Metrics (numeric scores)
    metrics: Dict[str, Dict[str, Any]]

    # Activities
    activities: List[NormalizedActivity]

    # Consumptions (food, drinks, meds)
    consumptions: List[NormalizedConsumption]

    # Social interactions
    social: List[Dict[str, Any]]

    # Sleep (special case)
    sleep: Optional[Dict[str, Any]]

    # Notes (goals, gratitude, symptoms, etc.)
    notes: List[Dict[str, Any]]

    # Locations visited
    locations: List[Dict[str, Any]] = field(default_factory=list)

    # Health symptoms
    health: List[Dict[str, Any]] = field(default_factory=list)

    # Gaps that need clarification
    gaps: List[DataGap] = field(default_factory=list)

    # Metadata
    quality: str = "medium"
    has_gaps: bool = False


# ============================================================================
# CONTROLLED VOCABULARY
# These would typically come from database but defined here for normalization
# ============================================================================


# Activity mappings: alias -> canonical_name
ACTIVITY_ALIASES = {
    # Running
    "jogging": "running",
    "jog": "running",
    "run": "running",
    "running": "running",
    # Gym/Exercise
    "gym": "gym",
    "gymming": "gym",
    "workout": "gym",
    "working out": "gym",
    "exercise": "gym",
    "exercising": "gym",
    "weights": "gym",
    "lifting": "gym",
    # Swimming
    "swimming": "swimming",
    "swim": "swimming",
    "swam": "swimming",
    # Cycling
    "cycling": "cycling",
    "biking": "cycling",
    "bike": "cycling",
    "cycle": "cycling",
    # Walking
    "walking": "walking",
    "walk": "walking",
    "walked": "walking",
    "stroll": "walking",
    # Yoga
    "yoga": "yoga",
    # Sports
    "badminton": "badminton",
    "cricket": "cricket",
    "football": "football",
    "soccer": "football",
    "basketball": "basketball",
    "tennis": "tennis",
    "table tennis": "table_tennis",
    "ping pong": "table_tennis",
    # Mental activities
    "reading": "reading",
    "read": "reading",
    "studying": "studying",
    "study": "studying",
    "studied": "studying",
    "learning": "learning",
    "programming": "programming",
    "coding": "programming",
    "code": "programming",
    "coded": "programming",
    "meditation": "meditation",
    "meditate": "meditation",
    "meditating": "meditation",
    # Creative
    "writing": "writing",
    "wrote": "writing",
    "drawing": "drawing",
    "painting": "painting",
    "music": "music_playing",
    # Leisure/Screen
    "netflix": "streaming",
    "watching": "watching_tv",
    "tv": "watching_tv",
    "youtube": "youtube",
    "gaming": "gaming",
    "games": "gaming",
    "instagram": "social_media",
    "insta": "social_media",
    "twitter": "social_media",
    "facebook": "social_media",
    "scrolling": "social_media",
    "reels": "social_media",
    # Chores
    "cooking": "cooking",
    "cooked": "cooking",
    "cleaning": "cleaning",
    "cleaned": "cleaning",
    "shopping": "shopping",
    "laundry": "laundry",
}

# Activity categories
ACTIVITY_CATEGORIES = {
    "running": "physical",
    "gym": "physical",
    "swimming": "physical",
    "cycling": "physical",
    "walking": "physical",
    "yoga": "physical",
    "badminton": "physical",
    "cricket": "physical",
    "football": "physical",
    "basketball": "physical",
    "tennis": "physical",
    "table_tennis": "physical",
    "dancing": "physical",
    "reading": "mental",
    "studying": "mental",
    "learning": "mental",
    "programming": "mental",
    "meditation": "mental",
    "writing": "creative",
    "drawing": "creative",
    "painting": "creative",
    "music_playing": "creative",
    "streaming": "leisure",
    "watching_tv": "leisure",
    "youtube": "leisure",
    "gaming": "leisure",
    "social_media": "leisure",
    "cooking": "chores",
    "cleaning": "chores",
    "shopping": "chores",
    "laundry": "chores",
}

# Screen time activities (for tracking)
SCREEN_TIME_ACTIVITIES = {
    "streaming",
    "watching_tv",
    "youtube",
    "gaming",
    "social_media",
    "programming",
}

# Calories per hour for activities (approximate)
ACTIVITY_CALORIES = {
    "running": 600,
    "gym": 400,
    "swimming": 550,
    "cycling": 500,
    "walking": 280,
    "yoga": 200,
    "badminton": 450,
    "cricket": 350,
    "football": 500,
    "basketball": 550,
    "tennis": 450,
    "dancing": 400,
}


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================


def normalize_activity_name(raw_name: str) -> Tuple[Optional[str], str]:
    """
    Normalize activity name to canonical form from controlled vocabulary.

    Args:
        raw_name: The raw activity name from user or extraction

    Returns:
        Tuple of (canonical_name, category). canonical_name is None if unknown.
    """
    raw_lower = raw_name.lower().strip()

    # Direct match
    if raw_lower in ACTIVITY_ALIASES:
        canonical = ACTIVITY_ALIASES[raw_lower]
        category = ACTIVITY_CATEGORIES.get(canonical, "other")
        return canonical, category

    # Partial match (contains)
    for alias, canonical in ACTIVITY_ALIASES.items():
        if alias in raw_lower or raw_lower in alias:
            category = ACTIVITY_CATEGORIES.get(canonical, "other")
            return canonical, category

    # Unknown - return None for canonical
    return None, "other"


def infer_time_of_day(
    time_str: Optional[str] = None, context_hints: Optional[List[str]] = None
) -> Optional[TimeOfDay]:
    """
    Infer time of day from time string or contextual hints.

    Args:
        time_str: Time in HH:MM format
        context_hints: List of text hints (e.g., ["morning workout"])

    Returns:
        TimeOfDay enum value or None
    """
    if time_str:
        try:
            hour = int(time_str.split(":")[0])
            if 4 <= hour < 7:
                return TimeOfDay.EARLY_MORNING
            elif 7 <= hour < 12:
                return TimeOfDay.MORNING
            elif 12 <= hour < 17:
                return TimeOfDay.AFTERNOON
            elif 17 <= hour < 21:
                return TimeOfDay.EVENING
            elif 21 <= hour < 24:
                return TimeOfDay.NIGHT
            else:
                return TimeOfDay.LATE_NIGHT
        except (ValueError, IndexError):
            pass

    if context_hints:
        hints_lower = " ".join(context_hints).lower()
        if any(w in hints_lower for w in ["morning", "woke up", "breakfast"]):
            return TimeOfDay.MORNING
        if any(w in hints_lower for w in ["afternoon", "lunch", "midday"]):
            return TimeOfDay.AFTERNOON
        if any(w in hints_lower for w in ["evening", "dinner", "sunset"]):
            return TimeOfDay.EVENING
        if any(w in hints_lower for w in ["night", "late", "before bed", "sleep"]):
            return TimeOfDay.NIGHT

    return None


def estimate_calories(activity: str, duration_minutes: Optional[int]) -> Optional[int]:
    """
    Estimate calories burned for an activity.

    Args:
        activity: Canonical activity name
        duration_minutes: Duration in minutes

    Returns:
        Estimated calories or None
    """
    if not duration_minutes or activity not in ACTIVITY_CALORIES:
        return None

    cal_per_hour = ACTIVITY_CALORIES[activity]
    return int(cal_per_hour * duration_minutes / 60)


# ============================================================================
# GAP DETECTION
# ============================================================================


def detect_gaps(raw_text: str, extraction: Dict[str, Any]) -> List[DataGap]:
    """
    Detect gaps in extraction that need user clarification.
    Skip if the activity is already extracted clearly.

    Args:
        raw_text: Original journal text
        extraction: Raw extraction from Gemini

    Returns:
        List of DataGap objects
    """
    gaps = []
    text_lower = raw_text.lower()

    # Get list of extracted activities to avoid false positive gap detection
    extracted_activities = set()
    for act in extraction.get("activities", []):
        if isinstance(act, dict):
            name = act.get("activity_name", "").lower()
            if name:
                extracted_activities.add(name)

    # Ambiguous activity mentions - only ask if activity not already extracted
    activity_patterns = [
        (r"played\s+(?:well|good|great|bad|poorly)(?!\w)", "What did you play?"),
        (r"went\s+(?:out|there)(?!\w)", "Where did you go?"),
        (r"did\s+(?:some|a lot of)\s+exercise", "What exercise did you do?"),
        (r"worked\s+out", "What workout did you do?"),
        (r"practiced(?!\s+\w+)", "What did you practice?"),
        (r"trained(?!\s+\w+)", "What did you train for?"),
    ]

    for pattern, question in activity_patterns:
        match = re.search(pattern, text_lower)
        if match:
            # Check if a related activity was already extracted
            # e.g., if "played badminton" is in text and "badminton" was extracted, skip
            already_resolved = False
            for activity_name in extracted_activities:
                if activity_name in text_lower:
                    already_resolved = True
                    break

            if not already_resolved:
                gaps.append(
                    DataGap(
                        field_category="activity",
                        question=question,
                        context=f"You mentioned: '{match.group(0)}'",
                        original_mention=match.group(0),
                        priority=GapPriority.HIGH,
                        suggested_options=[
                            "badminton",
                            "cricket",
                            "gym",
                            "running",
                            "yoga",
                        ],
                    )
                )

    # Ambiguous meal mentions
    meal_patterns = [
        (
            r"had\s+(?:some|a)\s+(?:food|meal|lunch|dinner|breakfast)",
            "What did you eat?",
        ),
        (r"ate\s+(?:something|well|good|out)", "What did you eat?"),
        (r"ordered\s+(?:food|something)", "What did you order?"),
    ]

    for pattern, question in meal_patterns:
        match = re.search(pattern, text_lower)
        if match:
            gaps.append(
                DataGap(
                    field_category="meal",
                    question=question,
                    context=f"You mentioned: '{match.group(0)}'",
                    original_mention=match.group(0),
                    priority=GapPriority.MEDIUM,
                )
            )

    # Duration missing for activities
    activities = extraction.get("activities", [])
    for activity in activities:
        if isinstance(activity, dict):
            activity_name = activity.get("activity_name", "").lower()
            if activity.get("duration_minutes") is None and activity_name:
                gaps.append(
                    DataGap(
                        field_category="activity",
                        question=f"How long did you do {activity.get('activity_name', 'this activity')}?",
                        context=f"Activity: {activity.get('activity_name')}",
                        original_mention=activity.get("raw_mention", ""),
                        priority=GapPriority.MEDIUM,
                        suggested_options=[
                            "15 minutes",
                            "30 minutes",
                            "1 hour",
                            "2 hours",
                        ],
                    )
                )

    # Sleep quality without hours
    sleep = extraction.get("sleep", {})
    if sleep:
        if sleep.get("quality") and not sleep.get("duration_hours"):
            gaps.append(
                DataGap(
                    field_category="sleep",
                    question="How many hours did you sleep?",
                    context="You mentioned sleep quality but not duration",
                    original_mention=sleep.get("raw_mention", ""),
                    priority=GapPriority.HIGH,
                )
            )

    return gaps


# ============================================================================
# GEMINI EXTRACTION SCHEMA
# ============================================================================


EXTRACTION_SCHEMA = """
{
  "sleep": {
    "duration_hours": "float (0-24)",
    "quality": "int (1-10)",
    "bedtime": "HH:MM (24h format)",
    "waketime": "HH:MM",
    "disruptions": "int",
    "nap_minutes": "int",
    "raw_mention": "exact text about sleep"
  },

  "metrics": {
    "mood_score": {"value": "int 1-10", "time_of_day": "morning|afternoon|evening|night"},
    "energy_level": {"value": "int 1-10", "time_of_day": "..."},
    "stress_level": {"value": "int 1-10", "time_of_day": "..."},
    "productivity_score": {"value": "int 1-10"},
    "water_intake_liters": {"value": "float"},
    "coffee_cups": {"value": "int"},
    "screen_time_hours": {"value": "float"}
  },

  "activities": [
    {
      "activity_name": "the activity (badminton, coding, netflix, etc.)",
      "duration_minutes": "int",
      "time_of_day": "morning|afternoon|evening|night",
      "start_time": "HH:MM if mentioned",
      "end_time": "HH:MM if mentioned",
      "intensity": "low|medium|high",
      "satisfaction": "int 1-10",
      "raw_mention": "exact text"
    }
  ],

  "meals": [
    {
      "meal_type": "breakfast|lunch|dinner|snack",
      "time_of_day": "morning|afternoon|evening|night",
      "meal_time": "HH:MM if mentioned",
      "items": [
        {
          "name": "food item name",
          "quantity": "float (e.g., 2 for 2 eggs)",
          "unit": "serving|piece|g|ml",
          "calories": "estimated calories (int)",
          "protein_g": "estimated protein in grams (float)",
          "carbs_g": "estimated carbs in grams (float)",
          "fat_g": "estimated fat in grams (float)",
          "fiber_g": "estimated fiber in grams (float, optional)",
          "sugar_g": "estimated sugar in grams (float, optional)",
          "sodium_mg": "estimated sodium in mg (float, optional)"
        }
      ],
      "is_healthy": "boolean",
      "is_home_cooked": "boolean",
      "raw_mention": "exact text"
    }
  ],

  "drinks": [
    {
      "drink_name": "water|coffee|tea|juice|etc",
      "quantity": "float",
      "unit": "cups|liters|glasses|ml",
      "calories": "estimated calories (int)",
      "time_of_day": "...",
      "raw_mention": "..."
    }
  ],

  "social": [
    {
      "person": "name or relationship (mom, friend, colleague)",
      "interaction_type": "in_person|call|video|message",
      "duration_minutes": "int",
      "time_of_day": "...",
      "sentiment": "positive|negative|neutral|conflict",
      "raw_mention": "..."
    }
  ],

  "notes": [
    {
      "type": "goal|achievement|gratitude|symptom|thought|plan",
      "content": "the note content",
      "sentiment": "positive|negative|neutral",
      "raw_mention": "..."
    }
  ],

  "locations": [
    {
      "location_name": "name of place (home, office, gym, cafe, park, mall, etc.)",
      "location_type": "home|office|gym|restaurant|cafe|outdoors|mall|hospital|school|other",
      "time_of_day": "morning|afternoon|evening|night",
      "duration_minutes": "int (how long at this location)",
      "activity_context": "what was done at this location",
      "raw_mention": "exact text mentioning the location"
    }
  ],

  "health": [
    {
      "symptom_type": "headache|fatigue|pain|nausea|fever|cold|cough|allergy|insomnia|anxiety|other",
      "body_part": "head|back|stomach|chest|throat|eyes|legs|arms|full_body|none",
      "severity": "int 1-10 (1=mild, 10=severe)",
      "duration_minutes": "int (optional)",
      "time_of_day": "morning|afternoon|evening|night",
      "possible_cause": "what might have caused it (optional)",
      "medication_taken": "any medication taken for it (optional)",
      "raw_mention": "exact text about the symptom"
    }
  ],

  "ambiguous": [
    {
      "text": "the ambiguous text",
      "question": "clarification question to ask",
      "field_category": "activity|meal|social|location|health|other",
      "suggestions": ["option1", "option2"]
    }
  ]
}
"""


# ============================================================================
# MAIN GEMINI EXTRACTOR
# ============================================================================


class GeminiExtractor:
    """
    Main extractor using Gemini for comprehensive journal analysis.

    Features:
    - Uses controlled vocabulary for normalization
    - Detects gaps and generates clarification questions
    - Tracks time of day for activities
    - Handles infinite variety of user data
    """

    def __init__(
        self,
        gemini_client: Optional[ResilientGeminiClient] = None,
        model: str = "gemini-2.5-flash",
    ):
        """
        Initialize the extractor.

        Args:
            gemini_client: Optional Gemini client instance
            model: Gemini model to use
        """
        self.gemini_client = gemini_client or ResilientGeminiClient()
        self.model = model

    async def extract_all(
        self,
        journal_text: str,
        user_context: Optional[Dict[str, Any]] = None,
        entry_date: Optional[date] = None,
    ) -> ExtractionResult:
        """
        Extract all data from journal entry with normalization and gap detection.

        Args:
            journal_text: The journal entry text
            user_context: Optional user baseline data for context
            entry_date: Date of the journal entry

        Returns:
            ExtractionResult with normalized data and any gaps
        """
        prompt = self._build_prompt(journal_text, user_context, entry_date)

        logger.debug(f"Extraction prompt length: {len(prompt)} chars")

        try:
            response = await self.gemini_client.generate_content(
                prompt=prompt,
                model=self.model,
            )

            raw_extraction = self._parse_response(response)

            # Normalize and detect gaps
            result = self._normalize_extraction(raw_extraction, journal_text)

            # Log summary
            self._log_summary(result)

            return result

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult(
                metrics={},
                activities=[],
                consumptions=[],
                social=[],
                sleep=None,
                notes=[],
                gaps=[],
            )

    def _build_prompt(
        self,
        journal_text: str,
        user_context: Optional[Dict[str, Any]],
        entry_date: Optional[date],
    ) -> str:
        """Build extraction prompt with instructions."""
        parts = []

        parts.append(
            """You are an intelligent journal analyzer for PLOS (Personal Life Operating System).

CRITICAL RULES:
1. Extract EVERYTHING mentioned - activities, food, mood, sleep, social, locations, health symptoms, etc.
2. Track TIME OF DAY for each item (morning, afternoon, evening, night)
3. For activities: extract exact duration if mentioned, or estimate from context
4. For food: list individual items with NUTRITION DATA (calories, protein, carbs, fat)
5. If something is AMBIGUOUS (e.g., "played well" - what was played?), add to "ambiguous" section
6. Include raw_mention - the exact text that mentioned each item
7. Use 24-hour format for times (HH:MM)

LOCATION EXTRACTION:
- Extract any places/locations mentioned (gym, cafe, mall, office, home, park, hospital, etc.)
- Include what activity was done at each location
- Common location types: home, office, gym, restaurant, cafe, outdoors, mall, hospital, school, other
- Example: "went to the gym" -> location: gym, activity_context: workout

HEALTH SYMPTOM EXTRACTION:
- Extract any health issues or symptoms mentioned (headache, fatigue, pain, nausea, cold, etc.)
- Include severity if mentioned (1-10 scale)
- Note any medication taken for it
- Note possible causes if mentioned
- Common symptoms: headache, fatigue, pain, nausea, fever, cold, cough, allergy, insomnia, anxiety

ACTIVITY NORMALIZATION:
- "jogging", "jog", "run" -> use "running"
- "gym", "workout", "exercising" -> use "gym"
- "coding", "programming" -> use "programming"
- "insta", "scrolling", "reels" -> use "social_media"
- Keep sport names as-is: badminton, cricket, football, etc.

DO NOT EXTRACT AS ACTIVITIES:
- Sleep-related: "going to bed", "sleeping", "waking up", "woke up", "going to sleep", "getting up", "got up"
- Rest-related: "rest", "resting", "nap", "napping", "relaxing"
- Eating mentions: "eating", "having food", "having breakfast", "having lunch", "having dinner"
- These belong in sleep or meals sections, NOT activities!

FOOD & NUTRITION EXTRACTION:
- Extract each food item separately with estimated nutrition values
- Estimate calories based on typical serving sizes and Indian food values
- Common Indian food calories (per serving):
  * Dosa: 120 cal, Idli: 80 cal, Vada: 180 cal, Poori: 150 cal
  * Rice (1 cup): 200 cal, Chapathi: 100 cal, Parotta: 200 cal
  * Dal/Sambar: 150 cal, Chicken curry: 250 cal, Egg: 78 cal
  * Biryani: 400 cal, Chicken (100g): 165 cal
  * Fruits bowl: 100 cal, Banana: 105 cal
- Multiply by quantity mentioned (e.g., "2 eggs" = 156 cal)
- Estimate protein, carbs, fat based on food type

TIME OF DAY:
- early_morning: 4am-7am
- morning: 7am-12pm
- afternoon: 12pm-5pm
- evening: 5pm-9pm
- night: 9pm-12am
- late_night: 12am-4am

"""
        )

        if entry_date:
            parts.append(f"## ENTRY DATE\n{entry_date.strftime('%A, %B %d, %Y')}\n\n")

        if user_context:
            baseline = user_context.get("baseline")
            if baseline:
                parts.append("## USER BASELINE (for reference)\n")
                # Handle both Pydantic model and dict formats
                if hasattr(baseline, "sleep_hours"):
                    # Pydantic model
                    avg_sleep = getattr(baseline, "sleep_hours", "?")
                    avg_mood = getattr(baseline, "mood_score", "?")
                    common_activities = getattr(baseline, "common_activities", []) or []
                else:
                    # Dict format
                    avg_sleep = (
                        baseline.get("avg_sleep_hours", "?")
                        if isinstance(baseline, dict)
                        else "?"
                    )
                    avg_mood = (
                        baseline.get("avg_mood_score", "?")
                        if isinstance(baseline, dict)
                        else "?"
                    )
                    common_activities = (
                        baseline.get("common_activities", [])
                        if isinstance(baseline, dict)
                        else []
                    )

                parts.append(f"- Typical sleep: {avg_sleep} hours\n")
                parts.append(f"- Typical mood: {avg_mood}/10\n")
                if common_activities:
                    parts.append(
                        f"- Common activities: {', '.join(common_activities)}\n\n"
                    )
                else:
                    parts.append("\n")

        parts.append("## JOURNAL ENTRY\n")
        parts.append(f'"""\n{journal_text}\n"""\n\n')

        parts.append("## EXTRACTION SCHEMA\n")
        parts.append(f"```json\n{EXTRACTION_SCHEMA}\n```\n\n")

        parts.append(
            """## RESPONSE
Return ONLY valid JSON. Include ONLY fields that have data.
For ambiguous items, generate a helpful clarification question.
"""
        )

        return "".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Gemini JSON response."""
        try:
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            return json.loads(cleaned.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {}

    def _normalize_extraction(
        self, raw: Dict[str, Any], journal_text: str
    ) -> ExtractionResult:
        """Normalize raw extraction to controlled vocabulary."""

        # Normalize activities
        activities = []
        for act in raw.get("activities", []):
            if not isinstance(act, dict):
                continue

            raw_name = act.get("activity_name", "")

            canonical, category = normalize_activity_name(raw_name)

            duration = act.get("duration_minutes")
            if isinstance(duration, str):
                try:
                    duration = int(duration)
                except ValueError:
                    duration = None

            time_of_day = None
            tod_str = act.get("time_of_day")
            if tod_str:
                try:
                    time_of_day = TimeOfDay(tod_str.lower())
                except ValueError:
                    time_of_day = infer_time_of_day(act.get("start_time"), [raw_name])

            activities.append(
                NormalizedActivity(
                    canonical_name=canonical,
                    raw_name=raw_name,
                    category=category,
                    duration_minutes=duration,
                    time_of_day=time_of_day,
                    start_time=act.get("start_time"),
                    end_time=act.get("end_time"),
                    intensity=act.get("intensity"),
                    satisfaction=act.get("satisfaction"),
                    calories_burned=(
                        estimate_calories(canonical, duration) if canonical else None
                    ),
                    is_screen_time=(
                        canonical in SCREEN_TIME_ACTIVITIES if canonical else False
                    ),
                    confidence=0.8 if canonical else 0.5,
                    needs_clarification=canonical is None,
                    raw_mention=act.get("raw_mention"),
                )
            )

        # Normalize meals/drinks -> consumptions
        consumptions = []

        # Map time_of_day to meal_type if meal_type is not proper
        def fix_meal_type(
            meal_type: Optional[str], time_of_day_str: Optional[str]
        ) -> Optional[str]:
            """Fix meal_type to be breakfast|lunch|dinner|snack."""
            valid_types = {"breakfast", "lunch", "dinner", "snack"}
            if meal_type and meal_type.lower() in valid_types:
                return meal_type.lower()
            # Infer from time_of_day if meal_type is wrong
            tod = (meal_type or time_of_day_str or "").lower()
            if tod in ("morning", "early_morning"):
                return "breakfast"
            elif tod == "afternoon":
                return "lunch"
            elif tod in ("evening", "night"):
                return "dinner"
            elif tod == "late_night":
                return "snack"
            return meal_type

        for meal in raw.get("meals", []):
            if not isinstance(meal, dict):
                continue

            time_of_day = None
            tod_str = meal.get("time_of_day")
            if tod_str:
                try:
                    time_of_day = TimeOfDay(tod_str.lower())
                except ValueError:
                    pass

            items = meal.get("items", [])
            if isinstance(items, str):
                items = [{"name": items}]

            for item in items:
                # Handle both old format (string) and new format (dict with nutrition)
                if isinstance(item, str):
                    item_name = item
                    item_data = {}
                else:
                    item_name = item.get("name", "")
                    item_data = item

                # Fix meal_type to proper values
                fixed_meal_type = fix_meal_type(meal.get("meal_type"), tod_str)

                consumptions.append(
                    NormalizedConsumption(
                        canonical_name=None,
                        raw_name=item_name,
                        consumption_type="meal",
                        meal_type=fixed_meal_type,
                        time_of_day=time_of_day,
                        consumption_time=meal.get("meal_time"),
                        quantity=item_data.get("quantity", 1.0),
                        unit=item_data.get("unit", "serving"),
                        calories=item_data.get("calories"),
                        protein_g=item_data.get("protein_g"),
                        carbs_g=item_data.get("carbs_g"),
                        fat_g=item_data.get("fat_g"),
                        fiber_g=item_data.get("fiber_g"),
                        sugar_g=item_data.get("sugar_g"),
                        sodium_mg=item_data.get("sodium_mg"),
                        is_healthy=meal.get("is_healthy"),
                        is_home_cooked=meal.get("is_home_cooked"),
                        raw_mention=meal.get("raw_mention"),
                    )
                )

        for drink in raw.get("drinks", []):
            if not isinstance(drink, dict):
                continue

            time_of_day = None
            tod_str = drink.get("time_of_day")
            if tod_str:
                try:
                    time_of_day = TimeOfDay(tod_str.lower())
                except ValueError:
                    pass

            consumptions.append(
                NormalizedConsumption(
                    canonical_name=None,
                    raw_name=drink.get("drink_name", ""),
                    consumption_type="drink",
                    meal_type=None,
                    time_of_day=time_of_day,
                    quantity=drink.get("quantity", 1),
                    unit=drink.get("unit", "ml"),
                    calories=drink.get("calories"),
                    raw_mention=drink.get("raw_mention"),
                )
            )

        # Normalize metrics
        metrics = {}
        for metric_name, metric_data in raw.get("metrics", {}).items():
            if isinstance(metric_data, dict):
                metrics[metric_name] = {
                    "value": metric_data.get("value"),
                    "time_of_day": metric_data.get("time_of_day"),
                    "confidence": 0.7,
                }
            elif isinstance(metric_data, (int, float)):
                metrics[metric_name] = {
                    "value": metric_data,
                    "confidence": 0.7,
                }

        # Social interactions
        social = []
        for s in raw.get("social", []):
            if isinstance(s, dict):
                social.append(s)

        # Notes
        notes = []
        for n in raw.get("notes", []):
            if isinstance(n, dict):
                notes.append(n)

        # Sleep
        sleep = raw.get("sleep")

        # Detect gaps from ambiguous section
        gaps = []
        for amb in raw.get("ambiguous", []):
            if isinstance(amb, dict):
                gaps.append(
                    DataGap(
                        field_category=amb.get("field_category", "other"),
                        question=amb.get("question", "Can you clarify?"),
                        context=f"You mentioned: '{amb.get('text', '')}'",
                        original_mention=amb.get("text", ""),
                        priority=GapPriority.MEDIUM,
                        suggested_options=amb.get("suggestions", []),
                    )
                )

        # Additional gap detection from patterns
        additional_gaps = detect_gaps(journal_text, raw)
        gaps.extend(additional_gaps)

        # Remove duplicate gaps
        seen = set()
        unique_gaps = []
        for gap in gaps:
            key = (gap.field_category, gap.original_mention)
            if key not in seen:
                seen.add(key)
                unique_gaps.append(gap)

        # Locations
        locations = []
        for loc in raw.get("locations", []):
            if isinstance(loc, dict):
                locations.append(loc)

        # Health symptoms
        health = []
        for h in raw.get("health", []):
            if isinstance(h, dict):
                health.append(h)

        return ExtractionResult(
            metrics=metrics,
            activities=activities,
            consumptions=consumptions,
            social=social,
            sleep=sleep,
            notes=notes,
            locations=locations,
            health=health,
            gaps=unique_gaps,
            has_gaps=len(unique_gaps) > 0,
            quality=self._calculate_quality(raw, unique_gaps),
        )

    def _calculate_quality(self, raw: Dict[str, Any], gaps: List[DataGap]) -> str:
        """Calculate extraction quality score."""
        score = 0

        # Points for having data
        if raw.get("sleep"):
            score += 15
        if raw.get("metrics"):
            score += 10
        if raw.get("activities"):
            score += 15
        if raw.get("meals"):
            score += 10
        if raw.get("social"):
            score += 5
        if raw.get("notes"):
            score += 5

        # Points for detail
        activities = raw.get("activities", [])
        for act in activities:
            if isinstance(act, dict):
                if act.get("duration_minutes"):
                    score += 5
                if act.get("time_of_day"):
                    score += 3

        # Penalty for gaps
        score -= len(gaps) * 5

        if score >= 50:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    def _log_summary(self, result: ExtractionResult) -> None:
        """Log extraction summary."""
        parts = []

        if result.sleep:
            hours = result.sleep.get("duration_hours")
            if hours:
                parts.append(f"sleep:{hours}h")

        if result.activities:
            parts.append(f"activities:{len(result.activities)}")

        if result.consumptions:
            parts.append(f"consumptions:{len(result.consumptions)}")

        if result.gaps:
            parts.append(f"gaps:{len(result.gaps)}")

        logger.info(
            f"Extraction: {', '.join(parts) or 'empty'} (quality: {result.quality})"
        )


# ============================================================================
# GAP RESOLVER WITH GEMINI PARAGRAPH PARSING
# ============================================================================


GAP_RESOLUTION_SCHEMA = """
{
  "resolved_gaps": [
    {
      "original_question": "the question that was asked",
      "answer_found": true/false,
      "extracted_data": {
        "field_category": "activity|meal|sleep|social|other",
        "value": "extracted value (activity name, food item, etc.)",
        "duration_minutes": "int if applicable",
        "time_of_day": "morning|afternoon|evening|night",
        "additional_details": {}
      },
      "confidence": 0.0-1.0
    }
  ],
  "new_data_found": {
    "activities": [],
    "consumptions": [],
    "social": [],
    "notes": [],
    "metrics": {}
  },
  "remaining_unclear": [
    {
      "question": "follow-up question if still unclear",
      "context": "what was mentioned but unclear"
    }
  ]
}
"""


class GapResolver:
    """
    Resolves data gaps using Gemini to parse user's paragraph responses.

    Unlike simple keyword matching, this uses AI to understand natural
    language responses like "Yeah I played badminton for about an hour
    in the morning, then had some dosa for breakfast."
    """

    def __init__(self, gemini_client: Optional[ResilientGeminiClient] = None):
        self.gemini_client = gemini_client or ResilientGeminiClient()

    async def resolve_gaps_from_paragraph(
        self,
        gaps: List[DataGap],
        user_paragraph: str,
        original_extraction: ExtractionResult,
    ) -> Tuple[ExtractionResult, List[DataGap]]:
        """
        Use Gemini to parse a paragraph response and resolve multiple gaps.

        The user can respond naturally like: "I played badminton for 45 mins
        in the morning. Had idli for breakfast around 9am."

        Args:
            gaps: List of gaps to resolve
            user_paragraph: User's natural language response
            original_extraction: The extraction result to update

        Returns:
            Tuple of (updated ExtractionResult, remaining unresolved gaps)
        """
        if not gaps or not user_paragraph.strip():
            return original_extraction, gaps

        prompt = self._build_gap_resolution_prompt(gaps, user_paragraph)

        try:
            response = await self.gemini_client.generate_content(
                prompt=prompt,
                model="gemini-2.5-flash",
            )

            parsed = self._parse_response(response)

            # Apply resolved gaps to extraction
            updated_extraction = self._apply_resolutions(
                original_extraction, parsed, gaps
            )

            # Determine remaining gaps
            remaining_gaps = self._get_remaining_gaps(gaps, parsed)

            # Add any new gaps from unclear items
            for unclear in parsed.get("remaining_unclear", []):
                remaining_gaps.append(
                    DataGap(
                        field_category="other",
                        question=unclear.get("question", "Can you clarify?"),
                        context=unclear.get("context", ""),
                        original_mention=unclear.get("context", ""),
                        priority=GapPriority.MEDIUM,
                    )
                )

            updated_extraction.gaps = remaining_gaps
            updated_extraction.has_gaps = len(remaining_gaps) > 0

            logger.info(
                f"Gap resolution: {len(gaps)} gaps -> {len(remaining_gaps)} remaining"
            )

            return updated_extraction, remaining_gaps

        except Exception as e:
            logger.error(f"Gap resolution failed: {e}")
            return original_extraction, gaps

    def _build_gap_resolution_prompt(
        self, gaps: List[DataGap], user_paragraph: str
    ) -> str:
        """Build prompt for gap resolution."""
        questions = []
        for i, gap in enumerate(gaps, 1):
            q = f"{i}. [{gap.field_category.upper()}] {gap.question}"
            if gap.context:
                q += f" (Context: {gap.context})"
            if gap.suggested_options:
                q += f" (Suggestions: {', '.join(gap.suggested_options)})"
            questions.append(q)

        return f"""You are resolving clarification questions from a journal entry.

QUESTIONS THAT NEED ANSWERS:
{chr(10).join(questions)}

USER'S RESPONSE:
\"\"\"{user_paragraph}\"\"\"

INSTRUCTIONS:
1. Extract answers to the above questions from the user's response
2. The user may answer naturally - parse their intent, not just keywords
3. Also extract any NEW information not related to the questions
4. If something is still unclear, generate a follow-up question
5. Normalize activity names (jogging -> running, gym -> gym, etc.)

For activities, extract: name, duration, time_of_day, intensity
For meals, extract: items, meal_type, time
For social, extract: person, interaction type, sentiment

RESPONSE SCHEMA:
```json
{GAP_RESOLUTION_SCHEMA}
```

Return ONLY valid JSON."""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Gemini JSON response."""
        try:
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Gap resolution JSON parse error: {e}")
            return {}

    def _apply_resolutions(
        self,
        extraction: ExtractionResult,
        parsed: Dict[str, Any],
        original_gaps: List[DataGap],
    ) -> ExtractionResult:
        """Apply resolved gaps and new data to extraction."""

        # Process resolved gaps
        for resolved in parsed.get("resolved_gaps", []):
            if not resolved.get("answer_found"):
                continue

            data = resolved.get("extracted_data", {})
            category = data.get("field_category", "other")

            if category == "activity":
                raw_name = data.get("value", "")
                canonical, cat = normalize_activity_name(raw_name)

                duration = data.get("duration_minutes")
                if isinstance(duration, str):
                    try:
                        duration = int(duration)
                    except ValueError:
                        duration = None

                time_of_day = None
                tod_str = data.get("time_of_day")
                if tod_str:
                    try:
                        time_of_day = TimeOfDay(tod_str.lower())
                    except ValueError:
                        pass

                extraction.activities.append(
                    NormalizedActivity(
                        canonical_name=canonical,
                        raw_name=raw_name,
                        category=cat,
                        duration_minutes=duration,
                        time_of_day=time_of_day,
                        start_time=None,
                        end_time=None,
                        intensity=data.get("additional_details", {}).get("intensity"),
                        satisfaction=None,
                        calories_burned=(
                            estimate_calories(canonical, duration)
                            if canonical
                            else None
                        ),
                        is_screen_time=(
                            canonical in SCREEN_TIME_ACTIVITIES if canonical else False
                        ),
                        confidence=resolved.get("confidence", 0.9),
                        needs_clarification=False,
                        raw_mention=data.get("value"),
                    )
                )

            elif category == "meal":
                time_of_day = None
                tod_str = data.get("time_of_day")
                if tod_str:
                    try:
                        time_of_day = TimeOfDay(tod_str.lower())
                    except ValueError:
                        pass

                extraction.consumptions.append(
                    NormalizedConsumption(
                        canonical_name=None,
                        raw_name=data.get("value", ""),
                        consumption_type="meal",
                        meal_type=data.get("additional_details", {}).get("meal_type"),
                        time_of_day=time_of_day,
                        consumption_time=data.get("additional_details", {}).get("time"),
                        confidence=resolved.get("confidence", 0.9),
                        raw_mention=data.get("value"),
                    )
                )

            elif category == "sleep":
                if extraction.sleep is None:
                    extraction.sleep = {}
                extraction.sleep["duration_hours"] = data.get("value")
                if data.get("additional_details"):
                    extraction.sleep.update(data["additional_details"])

            elif category == "social":
                extraction.social.append(
                    {
                        "person": data.get("value"),
                        "interaction_type": data.get("additional_details", {}).get(
                            "interaction_type"
                        ),
                        "sentiment": data.get("additional_details", {}).get(
                            "sentiment"
                        ),
                    }
                )

        # Process any new data found in the response
        new_data = parsed.get("new_data_found", {})

        for act in new_data.get("activities", []):
            if isinstance(act, dict):
                raw_name = act.get("activity_name", act.get("name", ""))
                canonical, cat = normalize_activity_name(raw_name)

                duration = act.get("duration_minutes")
                if isinstance(duration, str):
                    try:
                        duration = int(duration)
                    except ValueError:
                        duration = None

                extraction.activities.append(
                    NormalizedActivity(
                        canonical_name=canonical,
                        raw_name=raw_name,
                        category=cat,
                        duration_minutes=duration,
                        time_of_day=None,
                        start_time=None,
                        end_time=None,
                        intensity=act.get("intensity"),
                        satisfaction=None,
                        calories_burned=(
                            estimate_calories(canonical, duration)
                            if canonical
                            else None
                        ),
                        is_screen_time=(
                            canonical in SCREEN_TIME_ACTIVITIES if canonical else False
                        ),
                        confidence=0.85,
                        needs_clarification=False,
                        raw_mention=raw_name,
                    )
                )

        for meal in new_data.get("consumptions", []):
            if isinstance(meal, dict):
                extraction.consumptions.append(
                    NormalizedConsumption(
                        canonical_name=None,
                        raw_name=meal.get("name", ""),
                        consumption_type=meal.get("type", "meal"),
                        meal_type=meal.get("meal_type"),
                        time_of_day=None,
                        consumption_time=None,
                        confidence=0.85,
                        raw_mention=meal.get("name"),
                    )
                )

        return extraction

    def _get_remaining_gaps(
        self, original_gaps: List[DataGap], parsed: Dict[str, Any]
    ) -> List[DataGap]:
        """Determine which gaps were not resolved."""
        resolved_questions = set()

        for resolved in parsed.get("resolved_gaps", []):
            if resolved.get("answer_found"):
                resolved_questions.add(resolved.get("original_question", "").lower())

        remaining = []
        for gap in original_gaps:
            if gap.question.lower() not in resolved_questions:
                remaining.append(gap)

        return remaining

    async def resolve_single_gap(
        self,
        gap: DataGap,
        user_response: str,
        original_extraction: ExtractionResult,
    ) -> ExtractionResult:
        """
        Resolve a single gap with user's response (simple keyword approach for
        quick single answers).

        Args:
            gap: The gap being resolved
            user_response: User's answer to the clarification question
            original_extraction: The extraction result to update

        Returns:
            Updated ExtractionResult
        """
        if gap.field_category == "activity":
            canonical, category = normalize_activity_name(user_response)

            original_extraction.activities.append(
                NormalizedActivity(
                    canonical_name=canonical,
                    raw_name=user_response,
                    category=category,
                    duration_minutes=None,
                    time_of_day=None,
                    start_time=None,
                    end_time=None,
                    intensity=None,
                    satisfaction=None,
                    calories_burned=None,
                    is_screen_time=(
                        canonical in SCREEN_TIME_ACTIVITIES if canonical else False
                    ),
                    confidence=0.9,
                    needs_clarification=False,
                    raw_mention=gap.original_mention,
                )
            )

        original_extraction.gaps = [g for g in original_extraction.gaps if g != gap]
        original_extraction.has_gaps = len(original_extraction.gaps) > 0

        return original_extraction

    def format_gaps_for_user(self, gaps: List[DataGap]) -> List[Dict[str, Any]]:
        """
        Format gaps as questions for the user.

        Args:
            gaps: List of DataGap objects

        Returns:
            List of formatted question dictionaries
        """
        questions = []

        for gap in sorted(gaps, key=lambda g: g.priority.value):
            q = {
                "question": gap.question,
                "context": gap.context,
                "category": gap.field_category,
                "priority": gap.priority.name.lower(),
            }
            if gap.suggested_options:
                q["suggestions"] = gap.suggested_options

            questions.append(q)

        return questions

    def format_gaps_as_prompt(self, gaps: List[DataGap]) -> str:
        """
        Format gaps as a natural prompt for the user.

        Args:
            gaps: List of DataGap objects

        Returns:
            A natural language prompt asking all questions
        """
        if not gaps:
            return ""

        parts = ["I have a few questions about your journal entry:"]

        for i, gap in enumerate(sorted(gaps, key=lambda g: g.priority.value), 1):
            q = f"\n{i}. {gap.question}"
            if gap.suggested_options:
                q += f" (e.g., {', '.join(gap.suggested_options[:3])})"
            parts.append(q)

        parts.append("\n\nYou can answer naturally - just tell me the details!")

        return "".join(parts)


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================


async def extract_journal_entry(
    journal_text: str,
    user_context: Optional[Dict[str, Any]] = None,
    entry_date: Optional[date] = None,
    gemini_client: Optional[ResilientGeminiClient] = None,
) -> ExtractionResult:
    """
    Convenience function to extract data from a journal entry.

    Args:
        journal_text: The journal entry text
        user_context: Optional user baseline data
        entry_date: Date of the entry
        gemini_client: Optional Gemini client

    Returns:
        ExtractionResult with normalized data and gaps
    """
    extractor = GeminiExtractor(gemini_client=gemini_client)
    return await extractor.extract_all(journal_text, user_context, entry_date)
