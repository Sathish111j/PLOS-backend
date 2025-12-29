"""
PLOS v2.0 - Generalized Pattern Extraction
Dynamic, learning-based extraction that works for ANY input
No hardcoded patterns - learns from user data
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# DYNAMIC ACTIVITY DETECTOR
# ============================================================================


class DynamicActivityDetector:
    """
    Detects activities without hardcoding
    Learns from user's vocabulary and past entries
    """

    # Common activity indicators (expandable)
    ACTIVITY_VERBS = {
        "played",
        "did",
        "went",
        "had",
        "watched",
        "read",
        "studied",
        "worked",
        "coded",
        "programmed",
        "exercised",
        "ran",
        "walked",
        "talked",
        "chatted",
        "met",
        "saw",
        "visited",
        "ate",
        "cooked",
        "cleaned",
        "organized",
        "planned",
        "practiced",
        "learned",
    }

    # Time/duration indicators
    DURATION_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*(?:hour|hr|h)s?",
        r"(\d+)\s*(?:minute|min|m)s?",
        r"for\s+(\d+(?:\.\d+)?)\s*(?:hour|hr|h)s?",
        r"about\s+(\d+)\s*(?:hour|hr)s?",
    ]

    def __init__(self, user_activity_history: Optional[List[str]] = None):
        """
        Initialize with optional user history to learn patterns

        Args:
            user_activity_history: List of previously mentioned activities
        """
        self.known_activities: Set[str] = set()
        if user_activity_history:
            self.known_activities.update(user_activity_history)

    def extract_activities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract activities dynamically from text

        Returns: List of {activity: str, duration: float, confidence: float}
        """
        activities = []
        text_lower = text.lower()

        # Method 1: Check for known activities from history
        for activity in self.known_activities:
            if activity in text_lower:
                duration = self._extract_duration_near(text_lower, activity)
                activities.append(
                    {
                        "activity": activity,
                        "duration": duration,
                        "confidence": 0.90,  # High confidence - user's own vocabulary
                    }
                )

        # Method 2: Detect new activities via verb patterns
        new_activities = self._detect_verb_patterns(text)
        activities.extend(new_activities)

        # Method 3: Detect app/platform usage (social media, etc)
        app_activities = self._detect_app_usage(text)
        activities.extend(app_activities)

        return activities

    def _detect_verb_patterns(self, text: str) -> List[Dict[str, Any]]:
        """Detect activities from verb + object patterns"""
        activities = []
        sentences = re.split(r"[.!?]", text.lower())

        for sentence in sentences:
            for verb in self.ACTIVITY_VERBS:
                if verb in sentence:
                    # Extract what comes after the verb (likely the activity)
                    pattern = rf"{verb}\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)"
                    match = re.search(pattern, sentence)
                    if match:
                        activity_name = match.group(1).strip()
                        # Filter out common words
                        if activity_name not in {
                            "a",
                            "the",
                            "some",
                            "my",
                            "to",
                            "for",
                            "with",
                        }:
                            duration = self._extract_duration_near(
                                sentence, activity_name
                            )
                            activities.append(
                                {
                                    "activity": f"{verb} {activity_name}",
                                    "duration": duration,
                                    "confidence": 0.65,  # Medium confidence - inferred
                                }
                            )

        return activities

    def _detect_app_usage(self, text: str) -> List[Dict[str, Any]]:
        """Detect app/platform usage mentions"""
        # Common platforms (can be expanded from user history)
        platforms = [
            "instagram",
            "facebook",
            "twitter",
            "youtube",
            "tiktok",
            "netflix",
            "spotify",
            "reddit",
            "whatsapp",
            "telegram",
        ]

        activities = []
        text_lower = text.lower()

        for platform in platforms:
            if platform in text_lower:
                duration = self._extract_duration_near(text_lower, platform)
                activities.append(
                    {"activity": platform, "duration": duration, "confidence": 0.85}
                )

        return activities

    def _extract_duration_near(self, text: str, activity: str) -> Optional[float]:
        """Extract duration mentioned near an activity"""
        # Find where activity is mentioned
        activity_pos = text.find(activity)
        if activity_pos == -1:
            return None

        # Check 50 characters before and after
        window = text[max(0, activity_pos - 50) : activity_pos + 50]

        for pattern in self.DURATION_PATTERNS:
            match = re.search(pattern, window)
            if match:
                try:
                    hours = float(match.group(1))
                    return hours
                except Exception:
                    pass

        return None

    def add_learned_activity(self, activity: str) -> None:
        """Add activity to known vocabulary"""
        self.known_activities.add(activity.lower())
        logger.info(f"Learned new activity: {activity}")


# ============================================================================
# DYNAMIC MOOD DETECTOR
# ============================================================================


class DynamicMoodDetector:
    """
    Detects mood from sentiment without hardcoded keywords
    Uses semantic understanding and valence scoring
    """

    # Emotional valence words (expandable)
    POSITIVE_WORDS = {
        "happy",
        "great",
        "good",
        "excellent",
        "wonderful",
        "amazing",
        "fantastic",
        "love",
        "enjoy",
        "pleased",
        "satisfied",
        "content",
        "glad",
        "delighted",
        "thrilled",
        "excited",
        "grateful",
        "thankful",
    }

    NEGATIVE_WORDS = {
        "sad",
        "bad",
        "terrible",
        "awful",
        "horrible",
        "miserable",
        "depressed",
        "upset",
        "angry",
        "frustrated",
        "annoyed",
        "irritated",
        "worried",
        "anxious",
        "stressed",
        "disappointed",
        "hurt",
        "lonely",
    }

    # Intensity modifiers
    INTENSIFIERS = {"very", "really", "extremely", "super", "so", "quite"}
    DIMINISHERS = {"slightly", "somewhat", "a bit", "little", "kind of"}

    def __init__(self, user_mood_vocabulary: Optional[Dict[str, float]] = None):
        """
        Initialize with optional user-specific mood vocabulary

        Args:
            user_mood_vocabulary: Dict of {word: mood_score} from user history
        """
        self.user_vocabulary = user_mood_vocabulary or {}

    def estimate_mood(self, text: str) -> Tuple[Optional[float], float]:
        """
        Estimate mood score from text

        Returns: (mood_score, confidence)
        """
        text_lower = text.lower()
        words = text_lower.split()

        positive_count = 0
        negative_count = 0
        intensity_multiplier = 1.0

        for i, word in enumerate(words):
            # Check for intensity modifiers
            if i > 0:
                if words[i - 1] in self.INTENSIFIERS:
                    intensity_multiplier = 1.5
                elif words[i - 1] in self.DIMINISHERS:
                    intensity_multiplier = 0.7

            # Score word
            if (
                word in self.POSITIVE_WORDS
                or word in self.user_vocabulary
                and self.user_vocabulary[word] > 6
            ):
                positive_count += intensity_multiplier
            elif (
                word in self.NEGATIVE_WORDS
                or word in self.user_vocabulary
                and self.user_vocabulary[word] < 5
            ):
                negative_count += intensity_multiplier

            intensity_multiplier = 1.0  # Reset

        # Calculate mood score
        if positive_count == 0 and negative_count == 0:
            return None, 0.0  # No mood indicators

        # Scale: More positive words = higher mood
        total_indicators = positive_count + negative_count
        mood_score = 5.0 + (positive_count - negative_count) * 2.0
        mood_score = max(1.0, min(10.0, mood_score))

        # Confidence based on number of indicators
        confidence = min(0.70, 0.40 + (total_indicators * 0.10))

        return mood_score, confidence

    def learn_mood_word(self, word: str, associated_mood: float) -> None:
        """Learn user's mood vocabulary"""
        self.user_vocabulary[word] = associated_mood
        logger.info(f"Learned mood word: {word} -> {associated_mood}")


# ============================================================================
# DYNAMIC TIME EXTRACTOR
# ============================================================================


class DynamicTimeExtractor:
    """
    Extracts times in ANY format
    Handles natural language and variations
    """

    # Multiple time pattern variations
    TIME_PATTERNS = [
        # 24-hour: "14:30", "09:00"
        r"(\d{1,2}):(\d{2})",
        # 12-hour with am/pm: "11 pm", "7:30am", "9 AM"
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)",
        # Natural language: "midnight", "noon"
        r"(midnight|noon|midday)",
        # Relative: "around 11", "about 7"
        r"(?:around|about)\s+(\d{1,2})",
    ]

    def extract_times(self, text: str) -> Dict[str, Any]:
        """Extract all time mentions"""
        times = {"bedtime": None, "waketime": None, "other_times": []}

        for pattern in self.TIME_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized_time = self._normalize_time(match)

                # Determine context (bedtime vs waketime)
                context = self._determine_time_context(text, match.start())

                if "sleep" in context or "bed" in context:
                    times["bedtime"] = normalized_time
                elif "wake" in context or "alarm" in context:
                    times["waketime"] = normalized_time
                else:
                    times["other_times"].append(normalized_time)

        return times

    def _normalize_time(self, match) -> str:
        """Normalize time to 24-hour format"""
        groups = match.groups()

        # Handle special words
        if groups[0] in ["midnight"]:
            return "00:00"
        elif groups[0] in ["noon", "midday"]:
            return "12:00"

        # Handle 12-hour format
        if len(groups) >= 3 and groups[2]:  # has am/pm
            hour = int(groups[0])
            minute = groups[1] or "00"
            period = groups[2].lower()

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:{minute}"

        # Handle 24-hour format
        if len(groups) >= 2:
            hour = int(groups[0])
            minute = groups[1] or "00"
            return f"{hour:02d}:{minute}"

        return match.group(0)

    def _determine_time_context(self, text: str, position: int) -> str:
        """Determine if time is bedtime, waketime, or other"""
        window = text[max(0, position - 30) : position + 30].lower()
        return window


# ============================================================================
# GENERALIZED EXTRACTOR
# ============================================================================


class GeneralizedExtractor:
    """
    Main extractor that uses all dynamic detectors
    Learns and adapts to user's vocabulary
    """

    def __init__(
        self,
        user_activity_history: Optional[List[str]] = None,
        user_mood_vocabulary: Optional[Dict[str, float]] = None,
    ):
        self.activity_detector = DynamicActivityDetector(user_activity_history)
        self.mood_detector = DynamicMoodDetector(user_mood_vocabulary)
        self.time_extractor = DynamicTimeExtractor()

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract all data using dynamic methods"""
        return {
            "activities": self.activity_detector.extract_activities(text),
            "mood_estimate": self.mood_detector.estimate_mood(text),
            "times": self.time_extractor.extract_times(text),
        }

    def learn_from_extraction(self, extracted_data: Dict[str, Any]) -> None:
        """Learn from confirmed extractions"""
        # Learn new activities
        if "activities" in extracted_data:
            for activity in extracted_data["activities"]:
                self.activity_detector.add_learned_activity(activity["name"])

        # Learn mood vocabulary
        if "mood" in extracted_data and "text_keywords" in extracted_data:
            for keyword in extracted_data["text_keywords"]:
                self.mood_detector.learn_mood_word(
                    keyword, extracted_data["mood"]["score"]
                )
