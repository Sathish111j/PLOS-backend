"""
PLOS v2.0 - Enhanced Gemini Integration
Context-aware journal extraction using Gemini with comprehensive user data
"""

import json
from typing import Any, Dict, List, Optional

from shared.gemini.client import ResilientGeminiClient
from shared.models import (
    ExtractionType,
    FieldMetadata,
    RelationshipState,
    UserBaseline,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# CONTEXT-AWARE GEMINI EXTRACTOR
# ============================================================================

class ContextAwareGeminiExtractor:
    """
    Enhanced Gemini extractor that uses full user context for intelligent extraction
    """
    
    def __init__(
        self,
        gemini_client: Optional[ResilientGeminiClient] = None,
        model: str = "gemini-2.0-flash-exp"
    ):
        self.gemini_client = gemini_client or ResilientGeminiClient()
        self.model = model
    
    async def extract_with_context(
        self,
        journal_text: str,
        user_context: Dict[str, Any],
        explicit_extractions: Dict[str, FieldMetadata],
        inferred_extractions: Dict[str, FieldMetadata]
    ) -> Dict[str, FieldMetadata]:
        """
        Extract missing fields using Gemini with full context awareness
        
        Args:
            journal_text: The preprocessed journal entry text
            user_context: Full user context from ContextRetrievalEngine
            explicit_extractions: Fields extracted via regex (Tier 1)
            inferred_extractions: Fields inferred from rules (Tier 2/3)
        
        Returns:
            Dict of Gemini-extracted fields with metadata
        """
        # Build context-rich prompt
        prompt = self._build_context_prompt(
            journal_text,
            user_context,
            explicit_extractions,
            inferred_extractions
        )
        
        logger.debug(f"Sending context-aware prompt to Gemini ({len(prompt)} chars)")
        
        try:
            # Call Gemini with context
            response = await self.gemini_client.generate_content(
                prompt=prompt,
                model=self.model,
            )
            
            # Parse response
            gemini_extractions = self._parse_gemini_response(response)
            
            logger.info(f"Gemini extracted {len(gemini_extractions)} additional fields")
            return gemini_extractions
        
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            return {}
    
    def _build_context_prompt(
        self,
        journal_text: str,
        user_context: Dict[str, Any],
        explicit: Dict[str, FieldMetadata],
        inferred: Dict[str, FieldMetadata]
    ) -> str:
        """
        Build comprehensive prompt with user context
        """
        baseline = user_context.get("baseline", {})
        recent_entries = user_context.get("recent_entries", [])
        day_of_week_pattern = user_context.get("day_of_week_pattern", {})
        relationship_state = user_context.get("relationship_state", {})
        sleep_debt = user_context.get("sleep_debt", 0)
        activity_patterns = user_context.get("activity_patterns", [])
        
        prompt_parts = []
        
        # System instructions
        prompt_parts.append("""You are an intelligent journal entry analyzer for a personal life operating system (PLOS v2.0).

Your task is to extract structured data from a journal entry, using the user's historical context to fill in missing information intelligently.

CRITICAL INSTRUCTIONS:
1. Some fields are already extracted (EXPLICIT or INFERRED) - do NOT re-extract those
2. Focus ONLY on missing fields that you can reasonably infer from the text AND context
3. Use the user's baseline and recent patterns to make informed estimates
4. Provide confidence scores (0.0-1.0) reflecting your certainty
5. Include brief reasoning for each extraction
6. Return ONLY valid JSON matching the schema below

""")
        
        # User context
        if baseline:
            prompt_parts.append("## USER BASELINE (30-day average)\n")
            prompt_parts.append(f"- Sleep: {baseline.get('sleep_hours', 'unknown')}hrs (±{baseline.get('sleep_stddev', 0):.1f})\n")
            prompt_parts.append(f"- Mood: {baseline.get('mood_score', 'unknown')}/10 (±{baseline.get('mood_stddev', 0):.1f})\n")
            prompt_parts.append(f"- Energy: {baseline.get('energy_level', 'unknown')}/10\n")
            prompt_parts.append(f"- Stress: {baseline.get('stress_level', 'unknown')}/10\n\n")
        
        # Day-of-week pattern
        if day_of_week_pattern:
            prompt_parts.append(f"## TODAY'S TYPICAL PATTERN ({day_of_week_pattern.get('day_name', 'Unknown')})\n")
            if "sleep_baseline" in day_of_week_pattern:
                prompt_parts.append(f"- Typical sleep: {day_of_week_pattern['sleep_baseline']['value']}hrs\n")
            if "mood_baseline" in day_of_week_pattern:
                prompt_parts.append(f"- Typical mood: {day_of_week_pattern['mood_baseline']['value']}/10\n")
            prompt_parts.append("\n")
        
        # Relationship state
        if relationship_state:
            state = relationship_state.get("state", "UNKNOWN")
            days = relationship_state.get("days_in_state", 0)
            prompt_parts.append(f"## RELATIONSHIP STATE\n")
            prompt_parts.append(f"- Current state: {state} (day {days})\n")
            
            if state in ["CONFLICT", "COLD_WAR", "RECOVERY"]:
                prompt_parts.append(f"- IMPORTANT: Relationship stress likely impacting mood, sleep, and energy\n")
            
            prompt_parts.append("\n")
        
        # Sleep debt
        if sleep_debt > 0:
            prompt_parts.append(f"## SLEEP DEBT\n")
            prompt_parts.append(f"- Accumulated debt: {sleep_debt:.1f} hours\n")
            if sleep_debt > 5:
                prompt_parts.append(f"- HIGH DEBT: Likely impacting mood, energy, stress\n")
            prompt_parts.append("\n")
        
        # Recent entries (last 3 days for context)
        if recent_entries:
            prompt_parts.append("## RECENT HISTORY (last 3 days)\n")
            for i, entry in enumerate(recent_entries[-3:], 1):
                prompt_parts.append(f"Day -{4-i}:\n")
                if entry.get("sleep_hours"):
                    prompt_parts.append(f"  Sleep: {entry['sleep_hours']}hrs\n")
                if entry.get("mood_score"):
                    prompt_parts.append(f"  Mood: {entry['mood_score']}/10\n")
                if entry.get("activities"):
                    prompt_parts.append(f"  Activities: {', '.join(entry['activities'])}\n")
            prompt_parts.append("\n")
        
        # Activity patterns
        if activity_patterns:
            prompt_parts.append("## ACTIVITY IMPACT PATTERNS\n")
            for pattern in activity_patterns[:5]:  # Top 5
                activity = pattern.get("activity_type")
                mood_impact = pattern.get("avg_mood_impact", 0)
                energy_impact = pattern.get("avg_energy_impact", 0)
                
                prompt_parts.append(
                    f"- {activity}: mood {mood_impact:+.1f}, energy {energy_impact:+.1f}\n"
                )
            prompt_parts.append("\n")
        
        # Already extracted fields
        prompt_parts.append("## ALREADY EXTRACTED (do NOT re-extract these)\n")
        all_extracted = {**explicit, **inferred}
        if all_extracted:
            for field, meta in all_extracted.items():
                prompt_parts.append(f"- {field}: {meta.value} ({meta.type.value})\n")
        else:
            prompt_parts.append("- None yet\n")
        prompt_parts.append("\n")
        
        # Journal entry
        prompt_parts.append("## JOURNAL ENTRY\n")
        prompt_parts.append(f'"{journal_text}"\n\n')
        
        # Schema
        prompt_parts.append("""## EXTRACTION SCHEMA

Extract ONLY missing fields that you can reasonably infer. Return JSON format:

{
  "mood_score": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "energy_level": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "stress_level": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "sleep_quality": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "productivity_score": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "social_interaction_quality": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "gratitude_mentions": {
    "value": [<list of things mentioned with gratitude>],
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "challenges_mentioned": {
    "value": [<list of challenges/problems mentioned>],
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "goals_mentioned": {
    "value": [<list of goals/aspirations mentioned>],
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  },
  "relationship_quality": {
    "value": <1-10 integer>,
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
  }
}

IMPORTANT:
- Only include fields you can reasonably infer
- Use baseline and context to inform estimates
- Higher confidence (0.7-0.9) if explicitly mentioned
- Lower confidence (0.4-0.6) if inferred from context
- Very low confidence (0.2-0.4) if pure guess from baseline
- Include reasoning showing your thought process
- Return ONLY the JSON object, no additional text

""")
        
        return "".join(prompt_parts)
    
    def _parse_gemini_response(
        self,
        response: str
    ) -> Dict[str, FieldMetadata]:
        """
        Parse Gemini JSON response into FieldMetadata dict
        """
        extractions = {}
        
        try:
            # Clean response (sometimes Gemini adds markdown code blocks)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Convert to FieldMetadata
            for field, field_data in data.items():
                if not isinstance(field_data, dict):
                    logger.warning(f"Skipping invalid field format: {field}")
                    continue
                
                if "value" not in field_data:
                    logger.warning(f"Skipping field without value: {field}")
                    continue
                
                # Extract metadata
                value = field_data["value"]
                confidence = field_data.get("confidence", 0.5)
                reasoning = field_data.get("reasoning", "Extracted by Gemini")
                
                # Validate confidence
                if not (0.0 <= confidence <= 1.0):
                    logger.warning(f"Invalid confidence {confidence} for {field}, clamping to 0.5")
                    confidence = 0.5
                
                # Create FieldMetadata
                extractions[field] = FieldMetadata(
                    value=value,
                    type=ExtractionType.AI_EXTRACTED,
                    confidence=confidence,
                    source="gemini_context_aware",
                    reasoning=reasoning
                )
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            logger.debug(f"Raw response: {response[:500]}")
        
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
        
        return extractions
    
    async def generate_insights(
        self,
        all_extractions: Dict[str, FieldMetadata],
        user_context: Dict[str, Any],
        predictions: Dict[str, Any],
        health_alerts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate high-level insights and recommendations using Gemini
        
        This is called after extraction to provide meta-analysis
        """
        prompt = self._build_insights_prompt(
            all_extractions,
            user_context,
            predictions,
            health_alerts
        )
        
        try:
            response = await self.gemini_client.generate_content(
                prompt=prompt,
                model=self.model,
            )
            
            insights = json.loads(response.strip().replace("```json", "").replace("```", "").strip())
            
            logger.info("Generated insights from Gemini")
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            return {}
    
    def _build_insights_prompt(
        self,
        extractions: Dict[str, FieldMetadata],
        context: Dict[str, Any],
        predictions: Dict[str, Any],
        alerts: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for insights generation"""
        
        prompt = f"""You are a personal wellness coach analyzing a user's journal data.

## TODAY'S DATA
{json.dumps({k: v.value for k, v in extractions.items()}, indent=2)}

## BASELINE
{json.dumps(context.get("baseline", {}), indent=2)}

## PREDICTIONS (next day)
{json.dumps(predictions, indent=2)}

## HEALTH ALERTS
{json.dumps(alerts, indent=2)}

## RELATIONSHIP STATE
{json.dumps(context.get("relationship_state", {}), indent=2)}

Generate personalized insights in JSON format:

{{
  "key_observations": [
    "<observation 1>",
    "<observation 2>",
    "<observation 3>"
  ],
  "positive_patterns": [
    "<positive pattern 1>",
    "<positive pattern 2>"
  ],
  "areas_of_concern": [
    "<concern 1>",
    "<concern 2>"
  ],
  "actionable_recommendations": [
    "<recommendation 1>",
    "<recommendation 2>",
    "<recommendation 3>"
  ],
  "encouragement": "<brief encouraging message>",
  "focus_area": "<single most important area to focus on>"
}}

Be empathetic, specific, and actionable. Reference actual data points.
"""
        
        return prompt
