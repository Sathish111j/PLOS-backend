# PLOS Journal Processing Pipeline - Detailed Flow

> Complete documentation of the journal entry processing flow from user input to database storage.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [File Structure](#file-structure)
4. [Detailed Flow](#detailed-flow)
5. [Data Models](#data-models)
6. [Database Tables](#database-tables)
7. [Kafka Events](#kafka-events)

---

## Overview

When a user submits a journal entry, it flows through a **5-stage pipeline** with an optional **clarification loop**:

| Stage | Component | Purpose |
|-------|-----------|---------|
| 1 | Preprocessor | Text cleanup, spell correction, time normalization, explicit extraction |
| 2 | ContextRetrievalEngine | Fetch user baseline, patterns, relationship state |
| 3 | GeminiExtractor | AI-powered comprehensive extraction with gap detection |
| 3.5 | GapResolver (Loop) | Parse user's paragraph response to resolve gaps |
| 4 | StorageService | Normalized database storage with controlled vocabulary |
| 5 | ResponseAssembly | Format response with clarification questions |

**Key Design Principles:**
- Single Gemini call for comprehensive extraction (not multiple specialized calls)
- Controlled vocabulary for activities and consumptions
- Gap detection for ambiguous entries requiring user clarification
- **Paragraph-based gap resolution** - users answer naturally, Gemini parses
- Normalized relational storage (not JSON blobs)

---

## Architecture Diagram

```
                                    JOURNAL PROCESSING PIPELINE
                                    ============================

User Input                      API Gateway                     Journal Parser Service
+----------------+             +------------+                  +----------------------+
| "Woke up at    |   HTTP      |            |    HTTP          |                      |
|  7am, went     | ---------> |   Kong     | --------------> |      api.py          |
|  for a jog..." |   POST      |            |   /process       |   POST /process      |
+----------------+             +------------+                  +----------+-----------+
                                                                          |
                                                                          v
                                                               +----------------------+
                                                               |   orchestrator.py    |
                                                               | JournalParserOrch.   |
                                                               +----------+-----------+
                                                                          |
                    +-----------------------------------------------------+
                    |                         |                           |
                    v                         v                           v
         +------------------+     +---------------------+     +------------------------+
         | Stage 1:         |     | Stage 2:            |     | Stage 3:               |
         | preprocessing.py |     | context_retrieval.py|     | generalized_extraction |
         | - Spell correct  |     | - 30-day baseline   |     | - Gemini AI call       |
         | - Time normalize |     | - 7-day averages    |     | - Normalize vocab      |
         | - Explicit regex |     | - DOW patterns      |     | - Detect gaps          |
         | (+ Gemini clean) |     | - Relationship state|     | - Quality scoring      |
         +--------+---------+     | - Sleep debt        |     +------------+-----------+
                  |               +----------+----------+                  |
                  |                          |                             |
                  +--------------------------+-----------------------------+
                                             |
                                             v
                                  +----------------------+
                                  |     has_gaps?        |
                                  +----------+-----------+
                                             |
                         +-------------------+-------------------+
                         |Yes                                    |No
                         v                                       v
              +----------------------+                +----------------------+
              | Return with          |                |     Stage 4:         |
              | clarification        |                |  storage_service.py  |
              | questions            |                | - Store extraction   |
              +----------+-----------+                +----------+-----------+
                         |                                       |
                         v                                       v
              +----------------------+                +----------------------+
              | User responds with   |                | PostgreSQL + Kafka   |
              | paragraph answer     |                +----------------------+
              +----------+-----------+
                         |
                         v
              +----------------------+
              | POST /resolve-       |
              |   paragraph          |
              +----------+-----------+
                         |
                         v
              +----------------------+
              | Stage 3.5:           |
              | GapResolver          |
              | - Gemini parses      |
              |   paragraph          |
              | - Extract answers    |
              | - Find new data      |
              +----------+-----------+
                         |
                         v
              +----------------------+
              | All gaps resolved?   |----No----> Return remaining questions
              +----------+-----------+
                         |Yes
                         v
              +----------------------+
              | Update storage with  |
              | resolved data        |
              +----------------------+
```

---

## File Structure

```
services/journal-parser/src/
|-- api.py                    # HTTP endpoints (FastAPI router)
|-- orchestrator.py           # Pipeline coordinator (5 stages + gap loop)
|-- preprocessing.py          # Stage 1: Text preprocessing (+ optional Gemini)
|-- context_retrieval.py      # Stage 2: User context fetching
|-- generalized_extraction.py # Stage 3: Gemini AI extraction + GapResolver
|-- storage_service.py        # Stage 4: Database storage
|-- dependencies.py           # Dependency injection
|-- db_pool.py                # Database connection pool
|-- main.py                   # FastAPI application bootstrap
```

---

## Detailed Flow

### Entry Point: api.py

**Endpoint:** `POST /journal/process`

```python
# api.py - Lines 140-180
@router.post("/process", response_model=ExtractionResponse)
async def process_journal(
    request: JournalProcessRequest,
    db: AsyncSession = Depends(get_db_session),
    kafka: KafkaProducerService = Depends(get_kafka_producer),
    gemini: ResilientGeminiClient = Depends(get_gemini_client),
):
    orchestrator = JournalParserOrchestrator(
        db_session=db,
        kafka_producer=kafka,
        gemini_client=gemini,
    )
    result = await orchestrator.process_journal_entry(
        user_id=request.user_id,
        entry_text=request.entry_text,
        entry_date=request.entry_date,
    )
    return result
```

**Input:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "entry_text": "Woke up at 7am, slept 7 hours. Morning jog for 30 mins. Had oats for breakfast. Felt energetic all day. Met with Sarah for coffee.",
  "entry_date": "2024-01-15"
}
```

---

### Stage 1: Preprocessing (preprocessing.py)

**Purpose:** Clean and normalize text before AI extraction.

**Components:**

| Function | Purpose | Example |
|----------|---------|---------|
| `correct_spelling()` | Fix common typos | "exercised" -> "exercised", "gymming" -> "gym" |
| `normalize_times()` | Standardize time formats | "11 pm" -> "23:00", "7.30am" -> "07:30" |
| `ExplicitExtractor` | Regex-based extraction | Extract sleep hours, exercise duration |

**ExplicitExtractor Extracts:**

```python
class ExplicitExtractor:
    def extract(self, text: str) -> Dict[str, Any]:
        return {
            "sleep_hours": self._extract_sleep(text),       # "slept 7 hours" -> 7.0
            "exercise_duration": self._extract_exercise(text),  # "30 mins jog" -> 30
            "meals": self._extract_nutrition(text),         # meal mentions
            "work_hours": self._extract_work(text),         # work duration
            "activities": self._extract_activities(text),   # activity mentions
            "mood_indicators": self._extract_mood_indicators(text),  # mood words
            "has_conflict": self._check_conflict(text),     # conflict detection
        }
```

**Sleep Extraction Regex Patterns:**
```python
SLEEP_PATTERNS = [
    r"slept\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)",
    r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s+(?:of\s+)?sleep",
    r"got\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s+(?:of\s+)?sleep",
]
```

**Time Normalization:**
```python
def normalize_times(text: str) -> str:
    # "11 pm" -> "23:00"
    # "7.30am" -> "07:30"
    # "11:30 PM" -> "23:30"
```

**Output:** Tuple of (preprocessed_text, preprocessing_data, explicit_extractions)

**Optional: Gemini-Enhanced Preprocessing**

For messy inputs (voice-to-text, heavy abbreviations, mixed languages), use:

```python
# Optional Gemini-enhanced preprocessing
preprocessed_text, preprocessing_data, _ = await self.preprocessor.process_with_gemini(
    entry_text,
    gemini_client=self.gemini_client,
)
```

This uses a lightweight Gemini call to:
- Fix complex spelling errors
- Expand abbreviations ("bfast @ 9" -> "breakfast at 9:00")
- Clean voice-to-text artifacts
- Normalize informal writing

---

### Stage 2: Context Retrieval (context_retrieval.py)

**Purpose:** Fetch user historical data for intelligent extraction.

**Class:** `ContextRetrievalEngine`

**Key Method:** `get_full_context(user_id, entry_date)`

**Parallel Queries Executed:**
```python
results = await asyncio.gather(
    self.get_user_baseline(user_id, entry_date),      # 30-day averages
    self.get_recent_entries(user_id, entry_date),     # Last 7 entries
    self.get_day_of_week_pattern(user_id, weekday),   # DOW patterns
    self.get_relationship_state(user_id, entry_date), # Active relationships
    self.get_sleep_debt(user_id, entry_date),         # Accumulated sleep debt
    self.get_activity_patterns(user_id),              # Common activities
    return_exceptions=True,
)
```

**Context Data Structure:**
```python
context = {
    "baseline": {
        "avg_sleep_hours": 7.2,
        "avg_mood": 6.8,
        "avg_energy": 7.0,
        "avg_stress": 4.5,
        "std_sleep_hours": 0.8,
        "last_updated": "2024-01-14"
    },
    "recent_entries": [
        {"date": "2024-01-14", "mood": 7, "sleep": 7.5, "activities": ["gym"]},
        {"date": "2024-01-13", "mood": 6, "sleep": 6.0, "activities": ["reading"]},
        # ... last 7 entries
    ],
    "day_of_week_pattern": {
        "typical_wake_time": "07:00",
        "typical_bed_time": "23:00",
        "avg_mood": 7.2,
        "common_activities": ["running", "coffee"]
    },
    "relationship_state": {
        "name": "Sarah",
        "current_state": "connected",
        "last_interaction": "2024-01-10",
        "interaction_frequency": "weekly"
    },
    "sleep_debt": 2.5,  # hours below target accumulated
    "activity_patterns": [
        {"activity": "running", "frequency": 3, "avg_duration": 35},
        {"activity": "gym", "frequency": 2, "avg_duration": 60}
    ],
    "seven_day_context": {
        "avg_mood": 6.7,
        "avg_energy": 6.5,
        "avg_sleep": 6.8,
        "mood_trend": "improving"
    }
}
```

**UserBaseline Dataclass:**
```python
@dataclass
class UserBaseline:
    avg_sleep_hours: float = 7.5
    avg_mood: float = 6.0
    avg_energy: float = 6.0
    avg_stress: float = 5.0
    avg_exercise_minutes: float = 30.0
    std_sleep_hours: float = 1.0
    std_mood: float = 1.5
    common_activities: List[str] = field(default_factory=list)
    last_updated: Optional[date] = None
```

---

### Stage 3: Gemini Extraction (generalized_extraction.py)

**Purpose:** AI-powered comprehensive extraction with normalization.

**Class:** `GeminiExtractor`

**Key Method:** `extract_all(journal_text, user_context, entry_date)`

**Gemini Prompt Structure:**
```python
prompt = f"""
You are a life tracking assistant. Extract structured data from this journal entry.

USER CONTEXT:
- Baseline sleep: {context['baseline']['avg_sleep_hours']} hours
- Baseline mood: {context['baseline']['avg_mood']}/10
- Recent trend: {context['seven_day_context']['mood_trend']}
- Common activities: {context['activity_patterns']}

JOURNAL ENTRY:
{journal_text}

EXTRACT:
1. Sleep (hours, quality, times)
2. Metrics (mood, energy, stress - scale 1-10)
3. Activities (name, duration, intensity)
4. Consumptions (food, drinks, meds)
5. Social (who, interaction type, quality)
6. Notes (goals, gratitude, symptoms)
7. Gaps (ambiguous mentions needing clarification)

Return JSON in this schema:
{schema}
"""
```

**Controlled Vocabulary Normalization:**

```python
# Activity aliases -> canonical names
ACTIVITY_ALIASES = {
    "jogging": "running",
    "jog": "running",
    "gymming": "gym",
    "workout": "gym",
    "weights": "gym",
    "biking": "cycling",
    "swim": "swimming",
    # ... 80+ aliases
}

# Activity categories
ACTIVITY_CATEGORIES = {
    "running": "physical",
    "gym": "physical",
    "reading": "mental",
    "meditation": "mental",
    "streaming": "leisure",
    "gaming": "leisure",
    "cooking": "chores",
    # ... 40+ categories
}

# Screen time tracking
SCREEN_TIME_ACTIVITIES = {"streaming", "youtube", "gaming", "social_media"}

# Calorie estimation
ACTIVITY_CALORIES = {"running": 600, "gym": 400, "cycling": 500}  # per hour
```

**Normalization Function:**
```python
def normalize_activity_name(raw_name: str) -> Tuple[Optional[str], str]:
    """
    Returns: (canonical_name, category)
    - canonical_name is None if unknown activity
    """
    raw_lower = raw_name.lower().strip()
    
    # Direct match
    if raw_lower in ACTIVITY_ALIASES:
        canonical = ACTIVITY_ALIASES[raw_lower]
        return canonical, ACTIVITY_CATEGORIES.get(canonical, "other")
    
    # Partial match
    for alias, canonical in ACTIVITY_ALIASES.items():
        if alias in raw_lower:
            return canonical, ACTIVITY_CATEGORIES.get(canonical, "other")
    
    return None, "other"  # Unknown activity
```

**Gap Detection:**
```python
def detect_gaps(raw_text: str, extraction: Dict) -> List[DataGap]:
    gaps = []
    
    # Ambiguous activity patterns
    patterns = [
        (r"played\s+(?:well|good)", "What did you play?"),
        (r"went\s+(?:out|there)", "Where did you go?"),
        (r"worked\s+out", "What workout did you do?"),
    ]
    
    for pattern, question in patterns:
        if re.search(pattern, raw_text.lower()):
            gaps.append(DataGap(
                field_category="activity",
                question=question,
                priority=GapPriority.HIGH,
                suggested_options=["badminton", "cricket", "gym", "running"]
            ))
    
    # Missing duration for activities
    for activity in extraction.get("activities", []):
        if activity.get("duration_minutes") is None:
            gaps.append(DataGap(
                field_category="activity",
                question=f"How long did you do {activity['name']}?",
                priority=GapPriority.MEDIUM
            ))
    
    return gaps
```

**ExtractionResult Dataclass:**
```python
@dataclass
class ExtractionResult:
    metrics: Dict[str, Dict[str, Any]]       # mood, energy, stress with values
    activities: List[NormalizedActivity]     # normalized activities
    consumptions: List[NormalizedConsumption] # normalized food/drinks
    social: List[Dict[str, Any]]             # social interactions
    sleep: Optional[Dict[str, Any]]          # sleep data
    notes: List[Dict[str, Any]]              # goals, gratitude, symptoms
    gaps: List[DataGap]                      # clarification questions
    quality: str = "medium"                  # low/medium/high
    has_gaps: bool = False
```

**NormalizedActivity Dataclass:**
```python
@dataclass
class NormalizedActivity:
    canonical_name: Optional[str]  # From vocabulary (None if unknown)
    raw_name: str                  # Original text
    category: str                  # physical, mental, leisure, chores
    duration_minutes: Optional[int]
    time_of_day: Optional[TimeOfDay]
    start_time: Optional[str]      # HH:MM
    end_time: Optional[str]
    intensity: Optional[str]       # low, medium, high
    satisfaction: Optional[int]    # 1-10
    calories_burned: Optional[int]
    is_screen_time: bool = False
    confidence: float = 0.5
    needs_clarification: bool = False
```

**Quality Scoring:**
```python
def _calculate_quality(extraction: ExtractionResult) -> str:
    score = 0
    
    # Has sleep data (+30)
    if extraction.sleep and extraction.sleep.get("hours"):
        score += 30
    
    # Has mood (+20)
    if extraction.metrics.get("mood"):
        score += 20
    
    # Has activities (+20)
    if extraction.activities:
        score += 20
    
    # Has consumptions (+15)
    if extraction.consumptions:
        score += 15
    
    # Has social (+15)
    if extraction.social:
        score += 15
    
    # Penalty for gaps (-10 each)
    score -= len(extraction.gaps) * 10
    
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    return "low"
```

---

### Stage 3.5: Gap Clarification Loop (generalized_extraction.py)

**Purpose:** Resolve ambiguous entries through natural conversation.

**Class:** `GapResolver`

**Flow:**
```
Stage 3 completes with gaps
         |
         v
+--------------------+     
| Return response    |<----+
| with questions     |     |
+--------+-----------+     |
         |                 |
         v                 |
+--------------------+     |
| User responds      |     |
| (paragraph style)  |     |
+--------+-----------+     |
         |                 |
         v                 |
+--------------------+     |
| POST /resolve-     |     |
|   paragraph        |     |
+--------+-----------+     |
         |                 |
         v                 |
+--------------------+     |
| Gemini parses      |     |
| paragraph response |     |
+--------+-----------+     |
         |                 |
    Gaps remain? -----Yes--+
         |No
         v
+--------------------+
| Update storage     |
| with resolved data |
+--------------------+
```

**API Endpoint:** `POST /journal/resolve-paragraph`

```python
class ResolveParagraphRequest(BaseModel):
    user_id: UUID
    entry_id: UUID
    user_paragraph: str  # Natural language response

# Example request:
{
    "user_id": "...",
    "entry_id": "...",
    "user_paragraph": "I played badminton for about 45 minutes in the morning. Had idli and coffee for breakfast around 9am."
}
```

**GapResolver Key Methods:**

```python
class GapResolver:
    async def resolve_gaps_from_paragraph(
        self,
        gaps: List[DataGap],
        user_paragraph: str,
        original_extraction: ExtractionResult,
    ) -> Tuple[ExtractionResult, List[DataGap]]:
        """
        Use Gemini to parse natural language response.
        Returns updated extraction and remaining unresolved gaps.
        """
        prompt = self._build_gap_resolution_prompt(gaps, user_paragraph)
        response = await self.gemini_client.generate_content(prompt)
        
        # Apply resolved data to extraction
        updated = self._apply_resolutions(original_extraction, response, gaps)
        remaining = self._get_remaining_gaps(gaps, response)
        
        return updated, remaining

    def format_gaps_as_prompt(self, gaps: List[DataGap]) -> str:
        """
        Format gaps as natural prompt for user.
        
        Returns:
        "I have a few questions about your journal entry:
         1. What did you play? (e.g., badminton, cricket, tennis)
         2. What did you eat for breakfast?
         
         You can answer naturally - just tell me the details!"
        """
```

**Gap Resolution Prompt:**
```python
prompt = f"""You are resolving clarification questions from a journal entry.

QUESTIONS THAT NEED ANSWERS:
1. [ACTIVITY] What did you play? (Context: You mentioned 'played well')
2. [MEAL] What did you eat? (Context: You mentioned 'had breakfast')

USER'S RESPONSE:
\"\"\"I played badminton for 45 mins in the morning. Had idli and coffee.\"\"\"

INSTRUCTIONS:
1. Extract answers to the above questions
2. Parse natural language - user may not answer directly
3. Also extract any NEW information mentioned
4. If still unclear, generate follow-up questions

Return JSON with resolved_gaps, new_data_found, remaining_unclear
"""
```

**Response Structure:**
```python
{
    "entry_id": "uuid",
    "resolved_count": 2,
    "remaining_count": 0,
    "remaining_questions": [],  # Empty if all resolved
    "updated_activities": [
        {"name": "badminton", "duration_minutes": 45, "time_of_day": "morning"}
    ],
    "updated_consumptions": [
        {"name": "idli", "meal_type": "breakfast"},
        {"name": "coffee", "type": "drink"}
    ],
    "prompt_for_remaining": null  # Or follow-up prompt if gaps remain
}
```

---

### Stage 4: Storage (storage_service.py)

**Purpose:** Store extraction in normalized database tables.

**Class:** `StorageService`

**Key Method:** `store_extraction(user_id, entry_date, raw_entry, extraction)`

**Storage Sequence:**
```python
async def store_extraction(self, user_id, entry_date, raw_entry, extraction):
    # 1. Upsert base journal extraction
    extraction_id = await self._upsert_journal_entry(...)
    
    # 2. Store metrics (mood, energy, stress)
    await self._store_metrics(extraction_id, extraction.metrics)
    
    # 3. Store activities with vocabulary resolution
    await self._store_activities(extraction_id, extraction.activities)
    
    # 4. Store consumptions (food/drinks)
    await self._store_consumptions(extraction_id, extraction.consumptions)
    
    # 5. Store social interactions
    await self._store_social(extraction_id, extraction.social)
    
    # 6. Store notes (goals, gratitude)
    await self._store_notes(extraction_id, extraction.notes)
    
    # 7. Store sleep data
    await self._store_sleep(extraction_id, extraction.sleep)
    
    # 8. Store gaps for clarification
    await self._store_gaps(extraction_id, extraction.gaps)
    
    # 9. Commit transaction
    await self.db.commit()
    
    # 10. Publish Kafka event
    await self._publish_events(extraction_id, user_id, entry_date, extraction)
    
    return extraction_id
```

**Vocabulary Resolution (Activity Example):**
```python
async def _resolve_activity_type(self, name, raw_name, category) -> Optional[int]:
    # 1. Exact match on canonical_name
    result = await self.db.execute(
        "SELECT id FROM activity_types WHERE canonical_name = :name"
    )
    if result: return result
    
    # 2. Alias lookup
    result = await self.db.execute("""
        SELECT at.id FROM activity_types at
        JOIN activity_aliases aa ON at.id = aa.activity_type_id
        WHERE aa.alias = :alias
    """)
    if result: return result
    
    # 3. Fuzzy match (pg_trgm)
    result = await self.db.execute("""
        SELECT id, similarity(canonical_name, :name) as sim
        FROM activity_types WHERE canonical_name % :name
        ORDER BY sim DESC LIMIT 1
    """)
    if result and similarity > 0.3:
        await self._learn_activity_alias(name, result.id)  # Learn for future
        return result
    
    # 4. Create new activity type
    return await self._create_activity_type(name, raw_name, category)
```

---

### Stage 5: Response Assembly (orchestrator.py)

**Purpose:** Format extraction results for API response.

**Response Structure:**
```python
result = {
    "entry_id": "uuid",
    "user_id": "uuid",
    "entry_date": "2024-01-15",
    "quality": "high",
    
    # Extraction data
    "sleep": {
        "hours": 7.0,
        "quality": "good",
        "bed_time": "23:00",
        "wake_time": "07:00"
    },
    "metrics": {
        "mood": {"value": 8, "confidence": 0.9},
        "energy": {"value": 7, "confidence": 0.8},
        "stress": {"value": 3, "confidence": 0.7}
    },
    "activities": [
        {
            "name": "running",
            "category": "physical",
            "duration_minutes": 30,
            "time_of_day": "morning",
            "intensity": "medium",
            "calories": 300
        }
    ],
    "consumptions": [
        {
            "name": "oatmeal",
            "type": "meal",
            "meal_type": "breakfast",
            "time_of_day": "morning",
            "quantity": 1,
            "unit": "bowl"
        }
    ],
    "social": [
        {
            "person": "Sarah",
            "interaction_type": "meeting",
            "quality": "positive",
            "context": "coffee"
        }
    ],
    "notes": [
        {"type": "gratitude", "content": "Felt energetic all day"}
    ],
    
    # Gaps requiring clarification
    "has_gaps": false,
    "clarification_questions": [],
    
    # Metadata
    "metadata": {
        "processing_time_ms": 450,
        "preprocessing": {
            "spell_corrections": 0,
            "time_normalizations": 2
        }
    }
}
```

---

## Data Models

### TimeOfDay Enum
```python
class TimeOfDay(Enum):
    EARLY_MORNING = "early_morning"  # 4am - 7am
    MORNING = "morning"              # 7am - 12pm
    AFTERNOON = "afternoon"          # 12pm - 5pm
    EVENING = "evening"              # 5pm - 9pm
    NIGHT = "night"                  # 9pm - 12am
    LATE_NIGHT = "late_night"        # 12am - 4am
```

### GapPriority Enum
```python
class GapPriority(Enum):
    HIGH = 1    # Missing core data (sleep hours, activity type)
    MEDIUM = 2  # Missing details (duration, intensity)
    LOW = 3     # Nice to have (satisfaction, notes)
```

### DataGap Dataclass
```python
@dataclass
class DataGap:
    field_category: str           # 'activity', 'meal', 'sleep', 'social'
    question: str                 # "What did you play?"
    context: str                  # "You mentioned 'played well'"
    original_mention: str         # Exact ambiguous text
    priority: GapPriority = GapPriority.MEDIUM
    suggested_options: List[str] = field(default_factory=list)
```

---

## Database Tables

### Table: journal_extractions (Base Entry)
```sql
CREATE TABLE journal_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    entry_date DATE NOT NULL,
    raw_entry TEXT NOT NULL,
    overall_quality extraction_quality NOT NULL,
    has_gaps BOOLEAN DEFAULT false,
    extraction_time_ms INTEGER,
    gemini_model TEXT DEFAULT 'gemini-2.5-flash',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, entry_date)
);
```

### Table: extraction_metrics (Numeric Scores)
```sql
CREATE TABLE extraction_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    metric_type_id INTEGER REFERENCES metric_types(id),
    value NUMERIC(5,2) NOT NULL,
    time_of_day time_of_day,
    confidence NUMERIC(3,2) DEFAULT 0.7
);
```

### Table: extraction_activities
```sql
CREATE TABLE extraction_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    activity_type_id INTEGER REFERENCES activity_types(id),
    activity_raw TEXT,  -- NULL if resolved to vocabulary
    duration_minutes INTEGER,
    time_of_day time_of_day,
    start_time TIME,
    end_time TIME,
    intensity VARCHAR(10),
    satisfaction INTEGER CHECK (satisfaction BETWEEN 1 AND 10),
    calories_burned INTEGER,
    confidence NUMERIC(3,2),
    raw_mention TEXT,
    needs_clarification BOOLEAN DEFAULT false
);
```

### Table: extraction_consumptions
```sql
CREATE TABLE extraction_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    food_item_id INTEGER REFERENCES food_items(id),
    food_raw TEXT,
    consumption_type VARCHAR(20),  -- meal, snack, drink, medication
    meal_type VARCHAR(20),         -- breakfast, lunch, dinner
    time_of_day time_of_day,
    consumption_time TIME,
    quantity NUMERIC(5,2) DEFAULT 1,
    unit VARCHAR(20) DEFAULT 'serving',
    calories INTEGER,
    is_healthy BOOLEAN,
    is_home_cooked BOOLEAN,
    confidence NUMERIC(3,2)
);
```

### Table: extraction_social
```sql
CREATE TABLE extraction_social (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    person_name TEXT,
    relationship_type VARCHAR(50),
    interaction_type VARCHAR(50),
    quality VARCHAR(20),
    duration_minutes INTEGER,
    context TEXT
);
```

### Table: extraction_notes
```sql
CREATE TABLE extraction_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    note_type VARCHAR(50),  -- goal, gratitude, symptom, thought
    content TEXT,
    importance INTEGER CHECK (importance BETWEEN 1 AND 10)
);
```

### Table: extraction_sleep
```sql
CREATE TABLE extraction_sleep (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    hours NUMERIC(4,2),
    quality VARCHAR(20),
    bed_time TIME,
    wake_time TIME,
    interruptions INTEGER DEFAULT 0,
    dreams_noted BOOLEAN DEFAULT false
);
```

### Table: extraction_gaps (Clarification Queue)
```sql
CREATE TABLE extraction_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id),
    field_category VARCHAR(50),
    question TEXT,
    context TEXT,
    original_mention TEXT,
    priority INTEGER DEFAULT 2,
    suggested_options JSONB,
    resolved BOOLEAN DEFAULT false,
    user_response TEXT,
    resolved_at TIMESTAMPTZ
);
```

### Vocabulary Tables

```sql
-- Activity types (controlled vocabulary)
CREATE TABLE activity_types (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    category_id INTEGER REFERENCES activity_categories(id),
    calories_per_hour INTEGER,
    is_screen_time BOOLEAN DEFAULT false
);

-- Activity aliases (for normalization)
CREATE TABLE activity_aliases (
    id SERIAL PRIMARY KEY,
    activity_type_id INTEGER REFERENCES activity_types(id),
    alias VARCHAR(100) UNIQUE NOT NULL
);

-- Metric types
CREATE TABLE metric_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    unit VARCHAR(20) DEFAULT 'score',
    min_value NUMERIC DEFAULT 1,
    max_value NUMERIC DEFAULT 10
);
```

---

## Kafka Events

### Topic: JOURNAL_EXTRACTION_COMPLETE

**Published after:** Successful storage in Stage 4

**Event Schema:**
```json
{
  "event_type": "journal.extraction.complete",
  "timestamp": "2024-01-15T10:30:00Z",
  "payload": {
    "extraction_id": "uuid",
    "user_id": "uuid",
    "entry_date": "2024-01-15",
    "quality": "high",
    "has_gaps": false,
    "summary": {
      "activities_count": 1,
      "consumptions_count": 1,
      "social_count": 1,
      "gaps_count": 0
    }
  }
}
```

### Active Topics

| Topic | Purpose |
|-------|---------|
| JOURNAL_ENTRIES | New journal entries from API |
| PARSED_ENTRIES | Entries after preprocessing (legacy) |
| JOURNAL_EXTRACTION_COMPLETE | Full extraction result for downstream services |

---

## Error Handling

### Graceful Degradation
```python
# Context retrieval handles failures gracefully
results = await asyncio.gather(
    self.get_user_baseline(...),
    self.get_recent_entries(...),
    return_exceptions=True,  # Don't fail entire operation
)

if isinstance(baseline, Exception):
    logger.warning(f"Baseline retrieval failed: {baseline}")
    baseline = self._get_default_baseline()
```

### Database Transaction Safety
```python
try:
    await self._upsert_journal_entry(...)
    await self._store_metrics(...)
    await self._store_activities(...)
    await self.db.commit()
except Exception as e:
    await self.db.rollback()
    raise
```

---

## Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| Total processing time | 400-600ms |
| Gemini API call | 200-400ms |
| Context retrieval (parallel) | 50-100ms |
| Database storage | 30-50ms |
| Preprocessing | 5-10ms |

---

## Future Improvements

1. **Caching:** Cache user baselines (invalidate on new entry)
2. **Batch Processing:** Process multiple entries in single Gemini call
3. **Streaming:** Stream Gemini response for progressive UI updates
4. **Learning:** ML model to learn user vocabulary aliases
5. **Compression:** Compress raw_entry in database
