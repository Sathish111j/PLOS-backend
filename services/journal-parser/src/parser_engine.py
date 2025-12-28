"""
Parser Engine - Gemini-powered journal entry parser with structured outputs

Uses Gemini API to extract structured data from journal entries:
- Mood scores
- Health metrics (sleep, exercise, nutrition)
- Work focus levels
- Tags and categorization
"""

import json
from datetime import datetime
from typing import Optional

from google import genai
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel, Field

from shared.models.journal import ParsedJournalEntry
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ExtractedData(BaseModel):
    """Structured output schema for journal entry parsing"""

    mood_score: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Overall mood score (1-10)"
    )
    energy_level: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Energy level (1-10)"
    )
    stress_level: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Stress level (1-10)"
    )

    # Health metrics
    sleep_hours: Optional[float] = Field(
        None, ge=0.0, le=24.0, description="Hours of sleep"
    )
    sleep_quality: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Sleep quality (1-10)"
    )

    exercise_minutes: Optional[int] = Field(
        None, ge=0, description="Minutes of exercise"
    )
    exercise_type: Optional[str] = Field(
        None, description="Type of exercise (e.g., running, yoga)"
    )
    exercise_intensity: Optional[str] = Field(
        None, description="Exercise intensity: low/medium/high"
    )

    # Nutrition
    meals_count: Optional[int] = Field(
        None, ge=0, le=10, description="Number of meals/snacks"
    )
    water_intake: Optional[float] = Field(
        None, ge=0.0, description="Water intake in liters"
    )
    diet_quality: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Overall diet quality (1-10)"
    )

    # Work/Productivity
    work_hours: Optional[float] = Field(
        None, ge=0.0, le=24.0, description="Hours worked"
    )
    productivity_score: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Productivity score (1-10)"
    )
    focus_level: Optional[float] = Field(
        None, ge=1.0, le=10.0, description="Focus level (1-10)"
    )

    # Habits
    meditation_minutes: Optional[int] = Field(
        None, ge=0, description="Minutes of meditation"
    )
    reading_minutes: Optional[int] = Field(None, ge=0, description="Minutes of reading")
    social_interaction: Optional[str] = Field(
        None, description="Social interaction quality: low/medium/high"
    )

    # Meta
    tags: list[str] = Field(
        default_factory=list, description="Relevant tags/categories"
    )
    key_events: list[str] = Field(
        default_factory=list, description="Key events mentioned"
    )
    gratitude: Optional[str] = Field(None, description="Things user is grateful for")
    challenges: Optional[str] = Field(None, description="Challenges faced")


class JournalParserEngine:
    """
    Gemini-powered journal entry parser

    Uses Gemini's structured output capabilities to extract metrics from text
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """
        Initialize parser engine

        Args:
            api_key: Gemini API key
            model: Gemini model to use (default: gemini-2.0-flash-exp)
        """
        self.api_key = api_key
        self.model_name = model

        # Initialize Gemini client
        self.client = genai.Client(api_key=api_key)

        logger.info(f"Initialized JournalParserEngine with model: {model}")

    async def parse_entry(
        self, entry_text: str, user_id: Optional[str] = None
    ) -> ParsedJournalEntry:
        """
        Parse journal entry using Gemini structured outputs

        Args:
            entry_text: Raw journal entry text
            user_id: Optional user ID for context

        Returns:
            ParsedJournalEntry with extracted metrics
        """
        try:
            logger.info(f"Parsing journal entry (length: {len(entry_text)})")

            # Create system prompt
            system_prompt = """You are an expert at analyzing personal journal entries and extracting structured health, mood, and productivity data.

Your task:
1. Read the journal entry carefully
2. Extract all quantifiable metrics (mood, energy, sleep, exercise, nutrition, work, habits)
3. Return ONLY the structured JSON data - no explanations

Rules:
- Only extract data explicitly mentioned in the text
- Use null for missing values - DO NOT guess
- Scores should be on a 1-10 scale when applicable
- Tags should be relevant keywords (max 5-7 tags)
- Key events should be brief bullet points

Be precise and conservative - it's better to leave a field null than to guess."""

            # Create user prompt
            user_prompt = f"""Extract structured data from this journal entry:

{entry_text}

Return the data as JSON matching the schema."""

            # Configure structured output
            config = GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedData,
                temperature=0.1,  # Low temperature for consistent extraction
            )

            # Generate with structured output
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    {"role": "system", "parts": [{"text": system_prompt}]},
                    {"role": "user", "parts": [{"text": user_prompt}]},
                ],
                config=config,
            )

            # Parse response
            extracted_data = json.loads(response.text)
            logger.debug(f"Extracted data: {extracted_data}")

            # Convert to ParsedJournalEntry
            parsed_entry = ParsedJournalEntry(
                user_id=user_id,
                raw_content=entry_text,
                # Mood
                mood_score=extracted_data.get("mood_score"),
                energy_level=extracted_data.get("energy_level"),
                stress_level=extracted_data.get("stress_level"),
                # Health
                sleep_hours=extracted_data.get("sleep_hours"),
                sleep_quality=extracted_data.get("sleep_quality"),
                exercise_minutes=extracted_data.get("exercise_minutes"),
                exercise_type=extracted_data.get("exercise_type"),
                exercise_intensity=extracted_data.get("exercise_intensity"),
                # Nutrition
                meals_count=extracted_data.get("meals_count"),
                water_intake=extracted_data.get("water_intake"),
                diet_quality=extracted_data.get("diet_quality"),
                # Work
                work_hours=extracted_data.get("work_hours"),
                productivity_score=extracted_data.get("productivity_score"),
                focus_level=extracted_data.get("focus_level"),
                # Habits
                meditation_minutes=extracted_data.get("meditation_minutes"),
                reading_minutes=extracted_data.get("reading_minutes"),
                social_interaction=extracted_data.get("social_interaction"),
                # Meta
                tags=extracted_data.get("tags", []),
                key_events=extracted_data.get("key_events", []),
                gratitude=extracted_data.get("gratitude"),
                challenges=extracted_data.get("challenges"),
                parsed_at=datetime.utcnow(),
            )

            logger.info(
                f"Successfully parsed entry - extracted {sum(1 for v in extracted_data.values() if v is not None)} fields"
            )

            return parsed_entry

        except Exception as e:
            logger.error(f"Error parsing journal entry: {str(e)}")
            raise

    async def parse_batch(self, entries: list[str]) -> list[ParsedJournalEntry]:
        """
        Parse multiple journal entries in batch

        Args:
            entries: List of journal entry texts

        Returns:
            List of ParsedJournalEntry objects
        """
        parsed_entries = []

        for entry_text in entries:
            try:
                parsed = await self.parse_entry(entry_text)
                parsed_entries.append(parsed)
            except Exception as e:
                logger.error(f"Error parsing entry in batch: {str(e)}")
                # Continue with other entries
                continue

        logger.info(f"Batch parsed {len(parsed_entries)}/{len(entries)} entries")
        return parsed_entries
