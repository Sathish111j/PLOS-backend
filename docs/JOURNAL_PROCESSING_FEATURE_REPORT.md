# PLOS Journal Processing Feature - Detailed Technical Report

**Pull Request:** #20 - Journal Processing v0  
**Branch:** `journal_processing_v0` -> `main`  
**Changes:** +7,617 / -430 lines across 29 files  
**Date:** December 30, 2025

---

## Executive Summary

This PR introduces a comprehensive **AI-powered journal processing pipeline** that transforms free-form journal entries into structured, normalized data using Google Gemini AI. The system implements intelligent extraction with controlled vocabulary, gap detection for ambiguous entries, and multi-layer caching for performance optimization.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Database Schema](#2-database-schema)
3. [Kafka Event System](#3-kafka-event-system)
4. [Journal Parser Service](#4-journal-parser-service)
5. [Shared Models](#5-shared-models)
6. [API Endpoints](#6-api-endpoints)
7. [Data Flow](#7-data-flow)
8. [Key Features](#8-key-features)
9. [Configuration Changes](#9-configuration-changes)
10. [Testing](#10-testing)

---

## 1. Architecture Overview

### 1.1 System Design Philosophy

The journal processing system addresses four critical challenges:

| Problem | Solution |
|---------|----------|
| Users have infinite variety of hobbies, foods, activities | Controlled vocabulary tables with canonical names |
| Gemini might extract inconsistent field names | Generic extraction tables with foreign keys |
| Same activity could be categorized differently | Category hierarchy for flexible grouping |
| User input variations (typos, aliases) | Alias/synonym mapping with auto-learning |

### 1.2 Processing Pipeline

```
Journal Entry
     |
     v
+-------------------+
| 1. PREPROCESSING  |  Text normalization, spell correction
+-------------------+
     |
     v
+-------------------+
| 2. CONTEXT        |  Load user baseline, patterns, history
|    RETRIEVAL      |  Multi-layer cache: Memory -> Redis -> PostgreSQL -> Defaults
+-------------------+
     |
     v
+-------------------+
| 3. GEMINI         |  Comprehensive multi-field extraction
|    EXTRACTION     |  Using gemini-2.5-flash model
+-------------------+
     |
     v
+-------------------+
| 4. NORMALIZATION  |  Controlled vocabulary resolution
|    + GAP DETECT   |  Identify ambiguous entries for clarification
+-------------------+
     |
     v
+-------------------+
| 5. STORAGE        |  Normalized tables with alias learning
+-------------------+
     |
     v
+-------------------+
| 6. RESPONSE       |  Rich extraction results with gaps
|    ASSEMBLY       |  Publish events to Kafka
+-------------------+
```

---

## 2. Database Schema

**File:** `infrastructure/database/migrations/journal_schema.sql` (+685 lines)

### 2.1 PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- UUID generation (gen_random_uuid())
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Fuzzy text matching (trigram similarity)
```

### 2.2 Custom Enums

| Enum | Values | Purpose |
|------|--------|---------|
| `extraction_quality` | `high`, `medium`, `low` | Quality rating of extraction |
| `time_of_day` | `early_morning`, `morning`, `afternoon`, `evening`, `night`, `late_night` | Temporal context |
| `data_gap_status` | `pending`, `answered`, `skipped`, `expired` | Gap resolution states |

### 2.3 Controlled Vocabulary Tables

#### 2.3.1 Categories (Hierarchical)

```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,        -- canonical: "physical_activity"
    display_name VARCHAR(100) NOT NULL,       -- "Physical Activity"
    parent_id INT REFERENCES categories(id),  -- hierarchy support
    description TEXT,
    icon VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Pre-populated Categories:**

| Level | Categories |
|-------|------------|
| Top Level | wellness, activities, consumption, social, productivity, reflection |
| Wellness | sleep, mood, energy, stress, health |
| Activities | physical, mental, creative, leisure, chores |
| Consumption | meals, hydration, substances |

#### 2.3.2 Activity Types

```sql
CREATE TABLE activity_types (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,  -- "badminton", "running"
    display_name VARCHAR(100) NOT NULL,
    category_id INT NOT NULL REFERENCES categories(id),
    is_physical BOOLEAN DEFAULT FALSE,
    is_screen_time BOOLEAN DEFAULT FALSE,
    avg_calories_per_hour INT,
    typical_duration_minutes INT,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Pre-populated Activities (34 total):**

| Category | Activities |
|----------|------------|
| Physical | running, walking, cycling, swimming, gym, yoga, badminton, cricket, football, basketball, tennis, dancing |
| Mental | reading, studying, programming, learning, meditation, puzzles |
| Creative | writing, drawing, music_playing, photography |
| Leisure | watching_tv, gaming, social_media, netflix, youtube, music_listening |
| Chores | cooking, cleaning, shopping, laundry, gardening |

#### 2.3.3 Activity Aliases (Auto-Learning)

```sql
CREATE TABLE activity_aliases (
    id SERIAL PRIMARY KEY,
    alias VARCHAR(100) NOT NULL UNIQUE,       -- user's term: "jogging", "gymming"
    activity_type_id INT NOT NULL REFERENCES activity_types(id),
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(50) DEFAULT 'manual',      -- 'manual', 'learned', 'ai_suggested'
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Pre-populated Aliases (21 total):**
- `jogging`, `jog`, `run` -> running
- `gymming`, `workout`, `working out`, `exercise` -> gym
- `insta`, `instagram`, `twitter`, `facebook`, `scrolling` -> social_media
- `coding`, `code` -> programming
- And more...

#### 2.3.4 Food Items

```sql
CREATE TABLE food_items (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),  -- 'grain', 'protein', 'vegetable', 'fruit', 'dairy', 'junk'
    serving_size_g INT DEFAULT 100,
    calories_per_serving INT,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    is_healthy BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Pre-populated Foods (26 items):**

| Category | Items |
|----------|-------|
| Indian Staples | rice, roti, dal, sabzi, paratha, biryani, dosa, idli, samosa, paneer, curd |
| Western | chicken_breast, egg, oats, bread, pasta, pizza, burger, salad, fruits, milk |
| Beverages | coffee, tea, juice, soda, water |

#### 2.3.5 Metric Types

```sql
CREATE TABLE metric_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    category_id INT REFERENCES categories(id),
    unit VARCHAR(20),               -- 'hours', 'score_1_10', 'liters'
    min_value FLOAT,
    max_value FLOAT,
    description TEXT
);
```

**Pre-populated Metrics (11 types):**
- `sleep_duration`, `sleep_quality`
- `mood_score`, `energy_level`, `stress_level`
- `productivity_score`, `focus_level`
- `water_intake`, `coffee_cups`
- `work_hours`, `screen_time`

### 2.4 Core Extraction Tables

#### 2.4.1 Journal Extractions (Main Table)

```sql
CREATE TABLE journal_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    entry_date DATE NOT NULL,
    raw_entry TEXT NOT NULL,
    preprocessed_entry TEXT,
    overall_quality extraction_quality,
    extraction_time_ms INT,
    gemini_model VARCHAR(50),
    has_gaps BOOLEAN DEFAULT FALSE,
    gaps_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, entry_date)
);
```

#### 2.4.2 Extraction Sub-Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `extraction_metrics` | Numeric scores | metric_type_id, value, time_of_day, confidence |
| `extraction_activities` | Activity records | activity_type_id, duration_minutes, intensity, satisfaction |
| `extraction_consumptions` | Food/drink intake | food_item_id, consumption_type, meal_type, calories |
| `extraction_social` | Social interactions | person_name, relationship, interaction_type, sentiment |
| `extraction_notes` | Free-form notes | note_type (goal, gratitude, symptom), content, sentiment |
| `extraction_sleep` | Sleep details | duration_hours, quality, bedtime, waketime, disruptions |
| `extraction_gaps` | Clarification needed | question, context, priority, status, user_response |

### 2.5 Database Views

```sql
-- Activity summary with canonical names
CREATE VIEW v_activity_summary AS ...

-- Daily nutrition summary
CREATE VIEW v_daily_nutrition AS ...

-- Pending gaps for user
CREATE VIEW v_pending_gaps AS ...
```

### 2.6 Database Functions

```sql
-- Resolve activity name to canonical (exact -> alias -> fuzzy match)
CREATE FUNCTION resolve_activity_name(p_name VARCHAR) RETURNS INT

-- Get activity totals for date range
CREATE FUNCTION get_activity_totals(
    p_user_id UUID,
    p_start_date DATE,
    p_end_date DATE,
    p_category VARCHAR DEFAULT NULL
) RETURNS TABLE (...)
```

### 2.7 Indexes

| Table | Index | Type |
|-------|-------|------|
| categories | idx_categories_parent, idx_categories_name | B-tree |
| activity_types | idx_activity_types_category, idx_activity_types_search | B-tree, GIN |
| activity_aliases | idx_aliases_alias, idx_aliases_trgm | B-tree, GIN (trigram) |
| journal_extractions | idx_extractions_user_date | B-tree |
| extraction_gaps | idx_gaps_extraction, idx_gaps_status | B-tree |
| extraction_metrics | idx_metrics_extraction, idx_metrics_type | B-tree |
| extraction_activities | idx_activities_extraction, idx_activities_type, idx_activities_time | B-tree |
| extraction_consumptions | idx_consumptions_extraction, idx_consumptions_type, idx_consumptions_time | B-tree |
| extraction_social | idx_social_extraction, idx_social_person | B-tree |
| extraction_notes | idx_notes_extraction, idx_notes_type | B-tree |

---

## 3. Kafka Event System

**Files Modified:**
- `infrastructure/kafka/init-topics.sh` (+85 lines)
- `shared/kafka/topics.py` (+52 lines)
- `shared/kafka/producer.py` (+69 lines)
- `shared/kafka/consumer.py` (+107 lines)

### 3.1 Topic Naming Convention

Changed from underscore notation to **dot notation** (standard Kafka practice):

| Old Name | New Name |
|----------|----------|
| `journal_entries` | `plos.journal.entries` |
| `parsed_entries` | `plos.journal.parsed` |
| `mood_events` | `plos.mood.events` |
| `context_updates` | `plos.context.updates` |

### 3.2 New Topics Added

| Topic | Purpose | Retention |
|-------|---------|-----------|
| `plos.journal.entries.raw` | Raw journal entries | 7 days |
| `plos.journal.extraction.complete` | Extraction completion events | 7 days |
| `plos.sleep.data.extracted` | Sleep data events | 7 days |
| `plos.mood.data.extracted` | Mood data events | 7 days |
| `plos.relationship.events` | Relationship state changes | 7 days |
| `plos.relationship.state.changed` | State transition notifications | 7 days |
| `plos.health.alerts` | Health alert events | 7 days |
| `plos.health.alerts.triggered` | Triggered alert notifications | 7 days |
| `plos.predictions` | Prediction events | 1 day |
| `plos.predictions.generated` | Generated predictions | 1 day |

### 3.3 Async Kafka Services

**KafkaProducerService** (new async wrapper):
```python
class KafkaProducerService:
    async def start(self)
    async def stop(self)
    async def publish(topic: str, message: dict, key: str = None) -> bool
```

**KafkaConsumerService** (new async wrapper):
```python
class KafkaConsumerService:
    async def start(self)
    async def stop()
    async def consume(callback: Callable) -> None
    async def get_messages(timeout_ms: int) -> List[Dict]
```

---

## 4. Journal Parser Service

**Directory:** `services/journal-parser/src/`

### 4.1 New Files Added

| File | Lines | Purpose |
|------|-------|---------|
| `api.py` | 412 | FastAPI endpoints for journal processing |
| `orchestrator.py` | 328 | Main processing pipeline orchestrator |
| `preprocessing.py` | 497 | Text preprocessing with spell correction |
| `generalized_extraction.py` | 1,099 | Gemini extraction with normalization |
| `storage_service.py` | 911 | Database storage with vocabulary resolution |
| `context_retrieval.py` | 484 | User context and baseline retrieval |
| `cache_manager.py` | 336 | Multi-layer caching (Memory -> Redis -> DB) |
| `db_pool.py` | 383 | Connection pooling and query optimization |
| `dependencies.py` | 106 | FastAPI dependency injection |
| `worker.py` | 405 | Background processing worker |
| `quality_scoring.py` | 327 | Quality assessment system |
| `kafka_handler.py` | 106 (modified) | Kafka message handling |

### 4.2 Orchestrator (`orchestrator.py`)

The central coordinator for the extraction pipeline:

```python
class JournalParserOrchestrator:
    """
    Pipeline stages:
    1. Preprocessing
    2. Context Retrieval
    3. Gemini Extraction
    4. Normalization + Gap Detection
    5. Storage
    6. Response Assembly
    """
    
    async def process_journal_entry(
        self,
        user_id: UUID,
        entry_text: str,
        entry_date: Optional[date] = None,
    ) -> Dict[str, Any]
    
    async def resolve_gap(
        self,
        user_id: UUID,
        gap_id: UUID,
        user_response: str,
    ) -> Dict[str, Any]
    
    async def get_pending_gaps(self, user_id: UUID) -> List[Dict]
    async def get_activity_summary(self, user_id: UUID, days: int = 30) -> Dict
    async def get_user_activities(self, user_id: UUID, ...) -> List[Dict]
```

### 4.3 Preprocessing (`preprocessing.py`)

**Features:**
- Spell correction for common typos
- Time normalization (11pm -> 23:00)
- Duration parsing ("2 hours" -> 120 minutes)
- Explicit data extraction before AI processing

```python
class Preprocessor:
    def process(self, text: str) -> Tuple[str, Dict, Dict]:
        """
        Returns:
            - preprocessed_text: Cleaned and normalized text
            - preprocessing_data: Metadata about changes made
            - explicit_extractions: Data extracted explicitly from text
        """

class ExplicitExtractor:
    """Extract explicit mentions before Gemini processing"""
    def extract_all(self, text: str) -> Dict[str, FieldMetadata]
```

### 4.4 Generalized Extraction (`generalized_extraction.py`)

**Core Components:**

#### 4.4.1 Data Models

```python
class NormalizedActivity(BaseModel):
    raw_name: str
    canonical_name: Optional[str]
    category: str
    duration_minutes: Optional[int]
    time_of_day: Optional[TimeOfDay]
    intensity: Optional[str]
    satisfaction: Optional[int]
    calories_burned: Optional[int]
    confidence: float
    raw_mention: Optional[str]
    needs_clarification: bool = False

class NormalizedConsumption(BaseModel):
    raw_name: str
    canonical_name: Optional[str]
    consumption_type: str  # 'meal', 'snack', 'drink', 'medication'
    meal_type: Optional[str]  # 'breakfast', 'lunch', 'dinner'
    time_of_day: Optional[TimeOfDay]
    quantity: Optional[float]
    unit: Optional[str]
    calories: Optional[int]
    # ... nutritional data
    confidence: float
    raw_mention: Optional[str]

class DataGap(BaseModel):
    field_category: str
    question: str
    context: Optional[str]
    original_mention: Optional[str]
    priority: GapPriority

class ExtractionResult(BaseModel):
    quality: str  # 'high', 'medium', 'low'
    has_gaps: bool
    sleep: Optional[Dict]
    metrics: Dict[str, Dict]
    activities: List[NormalizedActivity]
    consumptions: List[NormalizedConsumption]
    social: List[Dict]
    notes: List[Dict]
    gaps: List[DataGap]
```

#### 4.4.2 GeminiExtractor

```python
class GeminiExtractor:
    """
    Comprehensive extraction using Gemini AI
    
    Features:
    - Structured prompt engineering
    - Multi-field extraction in single call
    - Normalization to controlled vocabulary
    - Gap detection for ambiguous entries
    - Confidence scoring
    """
    
    async def extract_all(
        self,
        journal_text: str,
        user_context: Dict[str, Any],
        entry_date: date,
    ) -> ExtractionResult
```

#### 4.4.3 GapResolver

```python
class GapResolver:
    """
    Handle ambiguous entries by generating clarification questions
    
    Gap Types:
    - Unknown activity (what sport did you play?)
    - Missing duration (how long did you exercise?)
    - Ambiguous meal (what did you have for breakfast?)
    - Unclear time (when did this happen?)
    """
    
    def format_gaps_for_user(
        self, 
        gaps: List[DataGap]
    ) -> List[Dict[str, Any]]
```

### 4.5 Storage Service (`storage_service.py`)

**Key Features:**
- Vocabulary resolution with fuzzy matching
- Alias auto-learning
- Upsert semantics (update if exists)
- Kafka event publishing

```python
class StorageService:
    """
    Tables used:
    - journal_extractions: Base entry record
    - extraction_metrics: Numeric scores
    - extraction_activities: Activities linked to activity_types
    - extraction_consumptions: Food/drinks linked to food_items
    - extraction_social: Social interactions
    - extraction_notes: Goals, gratitude, symptoms
    - extraction_sleep: Sleep data
    - extraction_gaps: Clarification questions
    """
    
    async def store_extraction(
        self,
        user_id: UUID,
        entry_date: date,
        raw_entry: str,
        extraction: ExtractionResult,
        extraction_time_ms: int,
        gemini_model: str,
    ) -> UUID
    
    # Vocabulary Resolution
    async def _resolve_activity_type(name, raw_name, category) -> Optional[int]
    async def _resolve_food_item(name, raw_name) -> Optional[int]
    async def _learn_activity_alias(alias, activity_type_id) -> None
```

**Vocabulary Resolution Flow:**

```
User Input: "jogging"
     |
     v
1. Exact Match: activity_types.canonical_name = 'jogging'
     |   (not found)
     v
2. Alias Lookup: activity_aliases.alias = 'jogging'
     |   (found: activity_type_id = running)
     v
Return: activity_types.id for 'running'

--- OR if not found ---

User Input: "badmington" (typo)
     |
     v
1. Exact Match: (not found)
     |
     v
2. Alias Lookup: (not found)
     |
     v
3. Fuzzy Match: pg_trgm similarity > 0.3
     |   (matches 'badminton' with similarity 0.91)
     v
4. Learn Alias: INSERT INTO activity_aliases ('badmington', badminton_id)
     |
     v
Return: activity_types.id for 'badminton'
```

### 4.6 Context Retrieval (`context_retrieval.py`)

```python
class ContextRetrievalEngine:
    """
    Retrieve user context for extraction:
    - User baseline (30-day averages)
    - Recent entries (7 days)
    - Day-of-week patterns
    - Relationship state
    - Sleep debt tracking
    - Activity impact history
    """
    
    async def get_full_context(
        self,
        user_id: UUID,
        entry_date: datetime,
    ) -> Dict[str, Any]
```

### 4.7 Cache Manager (`cache_manager.py`)

**4-Tier Caching Strategy:**

| Layer | Latency | Storage | TTL |
|-------|---------|---------|-----|
| L1: Memory | < 1ms | Process RAM | 6 hours |
| L2: Redis | 10-20ms | Distributed cache | 1 hour |
| L3: PostgreSQL | 100-500ms | Source of truth | Permanent |
| L4: Defaults | < 1ms | Hard-coded | N/A |

```python
class MemoryCache:
    """In-process memory cache with TTL and size limits"""
    max_size: int = 1000  # users
    ttl: timedelta = 6 hours
    
class MultiLayerCacheManager:
    """Cascading cache with fallback chain"""
    
    async def get_user_baseline(self, user_id: UUID) -> Dict[str, Any]:
        # Try L1 -> L2 -> L3 -> L4
    
    async def get_user_patterns(self, user_id: UUID) -> Dict[str, Any]
    async def get_activity_patterns(self, user_id: UUID) -> List
    async def invalidate_user_cache(self, user_id: UUID) -> None
```

### 4.8 Database Pool (`db_pool.py`)

**Connection Pool Configuration:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| pool_size | 5 | Minimum connections |
| max_overflow | 15 | Maximum additional connections |
| pool_recycle | 3600 | Recycle connections after 1 hour |
| pool_pre_ping | True | Test connections before use |
| pool_timeout | 30 | Wait up to 30s for connection |
| statement_timeout | 30s | Query timeout for safety |

```python
class DatabaseConnectionPool:
    """Production-grade async connection pooling"""
    
    async def initialize(self) -> None
    async def close(self) -> None
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]
    def get_pool_status(self) -> Dict[str, Any]

class QueryOptimizer:
    """Query optimization utilities"""
    
    @staticmethod
    async def parallel_queries(*queries) -> tuple
    
    @staticmethod
    async def parallel_with_timeout(*queries, timeout: float) -> tuple
```

### 4.9 Quality Scoring (`quality_scoring.py`)

**Quality Calculation:**

```
Base Score: 1.0

Penalties:
- Per inferred field: -0.05
- Per missing field: -0.03 to -0.10 (importance-weighted)
- Any inference_confidence < 0.50: -0.10
- Consistency check fails: -0.15
- Health alert triggered: -0.10
- Temporal inconsistency: -0.05
```

**Quality Levels:**

| Score Range | Level | Usage |
|-------------|-------|-------|
| 0.90+ | EXCELLENT | Trust for important decisions |
| 0.80-0.89 | VERY_GOOD | Good for analysis |
| 0.70-0.79 | GOOD | Acceptable for patterns |
| 0.60-0.69 | ACCEPTABLE | Use with caution |
| 0.50-0.59 | POOR | Informational only |
| < 0.50 | UNRELIABLE | Flag for clarification |

**Field Importance Weights:**

| Field | Penalty if Missing |
|-------|-------------------|
| sleep_hours, mood_score, energy_level | 0.10 (critical) |
| stress_level, sleep_quality | 0.07 (important) |
| productivity, work_hours, exercise | 0.05 (moderate) |
| nutrition, social, gratitude, goals | 0.03 (optional) |

---

## 5. Shared Models

**Files Added:**
- `shared/models/extraction.py` (+332 lines)
- `shared/models/patterns.py` (+364 lines)
- `shared/models/__init__.py` (+76 lines modified)

### 5.1 Extraction Models (`extraction.py`)

**Enums:**

```python
class RelationshipState(str, Enum):
    HARMONY = "HARMONY"
    TENSION = "TENSION"
    CONFLICT = "CONFLICT"
    COLD_WAR = "COLD_WAR"
    RECOVERY = "RECOVERY"
    RESOLVED = "RESOLVED"

class AlertLevel(str, Enum):
    INFO = "INFO"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ExtractionType(str, Enum):
    EXPLICIT = "explicit"      # Direct mention in text
    INFERRED = "inferred"      # Derived from context
    ESTIMATED = "estimated"    # Based on patterns
    DEFAULT = "default"        # Fallback value
    AI_EXTRACTED = "ai_extracted"  # Gemini extraction

class QualityLevel(str, Enum):
    EXCELLENT, VERY_GOOD, GOOD, ACCEPTABLE, POOR, UNRELIABLE
    HIGH, MEDIUM, LOW  # Aliases

class Trajectory(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"
```

**Core Models:**

```python
class FieldMetadata(BaseModel):
    """Metadata for each extracted field"""
    value: Optional[Any]
    type: ExtractionType
    confidence: float  # 0-1
    source: str
    user_said: Optional[str]  # Exact quote if explicit
    reasoning: Optional[str]  # Why inferred
    comparison_to_baseline: Optional[str]
    anomaly: bool = False
    health_concern: bool = False

class UserBaseline(BaseModel):
    """User's 30-day baseline metrics"""
    sleep_hours: float
    sleep_stddev: float
    mood_score: float
    mood_stddev: float
    energy_level: float
    stress_level: float
    sample_count: int
    last_updated: datetime
    day_of_week_patterns: Optional[Dict]

class JournalExtraction(BaseModel):
    """Complete journal extraction with intelligence"""
    id: Optional[UUID]
    user_id: UUID
    entry_date: date
    raw_entry: str
    extracted_data: ExtractedData
    extraction_metadata: ExtractionMetadata
    user_baseline: Optional[UserBaseline]
    relationship_state: Optional[RelationshipState]
    sleep_debt_cumulative: float
    fatigue_trajectory: Optional[Trajectory]
    mood_trajectory: Optional[Trajectory]
    anomalies_detected: List[str]
    health_alerts: List[str]
    clarification_needed: List[str]
```

### 5.2 Pattern Models (`patterns.py`)

```python
class UserPattern(BaseModel):
    """User pattern/baseline (sleep, mood, etc.)"""
    pattern_type: str
    value: Optional[float]
    std_dev: Optional[float]
    day_of_week: Optional[int]  # 0=Monday
    sample_count: int
    confidence: float

class RelationshipEvent(BaseModel):
    """Relationship state change event"""
    state_before: Optional[RelationshipState]
    state_after: RelationshipState
    trigger: Optional[str]
    severity: Optional[int]  # 1-10
    resolution_date: Optional[date]
    what_worked: Optional[str]

class ActivityImpact(BaseModel):
    """Activity impact correlation"""
    activity_type: str
    occurrence_count: int
    avg_mood_impact: Optional[float]
    avg_energy_impact: Optional[float]
    avg_sleep_impact: Optional[float]
    avg_satisfaction: Optional[float]

class SleepDebtLog(BaseModel):
    """Sleep debt tracking"""
    sleep_hours: Optional[float]
    baseline_hours: Optional[float]
    debt_this_day: Optional[float]
    debt_cumulative: Optional[float]
    recovery_sleep_needed: Optional[float]

class HealthAlert(BaseModel):
    """Health alert"""
    alert_level: AlertLevel
    alert_type: str
    alert_text: str
    recommendations: List[str]
    severity_score: Optional[float]
    requires_immediate_action: bool
    user_acknowledged: bool
    resolved: bool

class Prediction(BaseModel):
    """Prediction model"""
    predicted_sleep: Optional[float]
    predicted_mood: Optional[float]
    predicted_energy: Optional[float]
    week_forecast: Optional[Dict]
    activity_recommendations: Optional[Dict]

class ContextSummary(BaseModel):
    """Complete user context summary"""
    current_mood: Optional[float]
    current_energy: Optional[int]
    sleep_debt: float
    relationship_state: Optional[RelationshipState]
    mood_trend: Trajectory
    energy_trend: Trajectory
    active_health_alerts: List[HealthAlert]
    top_mood_boosters: List[str]
    recommendations: List[str]
```

---

## 6. API Endpoints

**File:** `services/journal-parser/src/api.py`

### 6.1 Process Journal Entry

```http
POST /journal/process
Content-Type: application/json

{
    "user_id": "uuid",
    "entry_text": "Journal text...",
    "entry_date": "2025-12-30"  // optional, defaults to today
}
```

**Response:**

```json
{
    "entry_id": "uuid",
    "user_id": "uuid",
    "entry_date": "2025-12-30",
    "quality": "high",
    "sleep": {
        "duration_hours": 7.5,
        "quality": 8,
        "bedtime": "23:00",
        "waketime": "06:30"
    },
    "metrics": {
        "mood_score": {"value": 7, "confidence": 0.85},
        "energy_level": {"value": 8, "confidence": 0.90}
    },
    "activities": [
        {
            "name": "badminton",
            "category": "physical",
            "duration_minutes": 60,
            "time_of_day": "evening",
            "intensity": "high",
            "calories": 450
        }
    ],
    "consumptions": [
        {
            "name": "rice",
            "type": "meal",
            "meal_type": "lunch",
            "time_of_day": "afternoon",
            "quantity": 1,
            "unit": "serving"
        }
    ],
    "social": {...},
    "notes": {...},
    "has_gaps": true,
    "clarification_questions": [
        {
            "question": "What kind of exercise did you do?",
            "context": "You mentioned 'worked out' but didn't specify",
            "category": "activity",
            "priority": "medium",
            "suggestions": ["gym", "running", "yoga"]
        }
    ],
    "processing_time_ms": 1234
}
```

### 6.2 Resolve Gap

```http
POST /journal/resolve-gap
Content-Type: application/json

{
    "gap_id": "uuid",
    "user_response": "I did yoga for 30 minutes"
}
```

### 6.3 Get Pending Gaps

```http
GET /journal/pending-gaps/{user_id}
```

### 6.4 Get User Activities

```http
GET /journal/activities/{user_id}?start_date=2025-12-01&end_date=2025-12-30&category=physical
```

### 6.5 Get Activity Summary

```http
GET /journal/activity-summary/{user_id}?days=30
```

### 6.6 Health Check

```http
GET /journal/health
```

### 6.7 Service Metrics

```http
GET /journal/metrics
```

---

## 7. Data Flow

### 7.1 Journal Processing Flow

```
User submits journal entry
         |
         v
+------------------+
| FastAPI Endpoint |
| POST /process    |
+------------------+
         |
         v
+------------------+
| Orchestrator     |
| process_entry()  |
+------------------+
         |
    +----+----+
    |         |
    v         v
+-------+  +----------+
| Prep- |  | Context  |
| rocess|  | Retrieve |
+-------+  +----------+
    |         |
    +----+----+
         |
         v
+------------------+
| Gemini Extractor |
| extract_all()    |
+------------------+
         |
         v
+------------------+
| Storage Service  |
| store_extraction |
+------------------+
    |         |
    v         v
+-------+  +-------+
| Post- |  | Kafka |
| greSQL|  | Event |
+-------+  +-------+
         |
         v
    Response with
    clarification
    questions
```

### 7.2 Vocabulary Resolution Flow

```
Activity: "played badminton for an hour"
                    |
                    v
            +----------------+
            | Raw Extraction |
            | "badminton"    |
            +----------------+
                    |
                    v
            +----------------+
            | Exact Match?   |-----> Yes --> Return ID
            | activity_types |
            +----------------+
                    |
                    No
                    v
            +----------------+
            | Alias Match?   |-----> Yes --> Return ID
            | activity_alias |
            +----------------+
                    |
                    No
                    v
            +----------------+
            | Fuzzy Match?   |-----> Yes --> Learn Alias
            | pg_trgm > 0.3  |              --> Return ID
            +----------------+
                    |
                    No
                    v
            +----------------+
            | Create New     |
            | activity_type  |
            +----------------+
                    |
                    v
               Return ID
```

---

## 8. Key Features

### 8.1 Controlled Vocabulary System

- **Canonical Names**: Single source of truth for each activity/food
- **Alias Learning**: System learns user's terminology over time
- **Fuzzy Matching**: Handles typos using PostgreSQL pg_trgm
- **Hierarchical Categories**: Flexible grouping and filtering

### 8.2 Gap Detection

When Gemini cannot confidently extract data, it generates clarification questions:

| Gap Type | Example Question |
|----------|------------------|
| Unknown activity | "What sport did you play when you mentioned 'played well'?" |
| Missing duration | "How long did you exercise?" |
| Ambiguous meal | "What did you have for breakfast?" |
| Unclear time | "When did you go to the gym - morning or evening?" |
| Unknown food | "What was the 'special dish' you mentioned?" |

### 8.3 Quality Scoring

Every extraction gets a quality score based on:
- Explicit vs inferred data
- Confidence levels
- Completeness
- Consistency checks
- Health alert triggers

### 8.4 Multi-Layer Caching

```
Request for User Baseline
         |
    +----v----+
    | Memory  | < 1ms, 6 hour TTL
    | Cache   |
    +---------+
         |
    Miss |
    +----v----+
    | Redis   | 10-20ms, 1 hour TTL
    | Cache   |
    +---------+
         |
    Miss |
    +----v----+
    | Postgres| 100-500ms, permanent
    | Query   |
    +---------+
         |
    Miss |
    +----v----+
    | Default | < 1ms, hard-coded
    | Values  |
    +---------+
```

### 8.5 Relationship State Machine

Tracks relationship status transitions:

```
HARMONY --> TENSION --> CONFLICT --> COLD_WAR
    ^          |           |            |
    |          v           v            v
    +------- RECOVERY <-- RESOLVED <---+
```

### 8.6 Sleep Debt Tracking

Cumulative sleep debt calculation with recovery predictions.

### 8.7 Activity Impact Correlation

Learns which activities positively/negatively impact:
- Mood
- Energy
- Sleep quality
- Stress levels

---

## 9. Configuration Changes

### 9.1 Requirements Added

**File:** `services/journal-parser/requirements.txt`

```
aiohttp==3.9.1  # HTTP Client for async requests
```

### 9.2 Prometheus Configuration

**File:** `infrastructure/monitoring/prometheus.yml`

Added YAML document start marker `---` for proper parsing.

### 9.3 Version Update

**File:** `services/journal-parser/src/__init__.py`

```python
__version__ = "2.0.0"  # was "1.0.0"
```

---

## 10. Testing

**File:** `services/journal-parser/tests/test_extraction.py` (+388 lines)

### 10.1 Test Categories

| Category | Tests |
|----------|-------|
| Preprocessing | Spell correction, time normalization, explicit extraction |
| Inference Engine | Energy inference, stress inference |
| Relationship State | State transitions, mood impact |
| Health Monitor | Sleep debt alerts, mood volatility |
| Prediction Engine | Sleep prediction, mood prediction |
| Integration | Full pipeline with mocks |

### 10.2 Test Fixtures

```python
@pytest.fixture
def sample_baseline() -> UserBaseline

@pytest.fixture
def sample_user_id() -> UUID

@pytest.fixture
def sample_journal_entry() -> str
```

---

## Appendix A: File Changes Summary

| File | Change Type | Lines |
|------|-------------|-------|
| `infrastructure/database/migrations/journal_schema.sql` | Added | +685 |
| `infrastructure/kafka/init-topics.sh` | Modified | +85/-21 |
| `infrastructure/monitoring/prometheus.yml` | Modified | +1 |
| `services/context-broker/src/main.py` | Modified | +2/-2 |
| `services/journal-parser/requirements.txt` | Modified | +3 |
| `services/journal-parser/src/__init__.py` | Modified | +13/-4 |
| `services/journal-parser/src/api.py` | Added | +412 |
| `services/journal-parser/src/cache_manager.py` | Added | +336 |
| `services/journal-parser/src/context_retrieval.py` | Added | +484 |
| `services/journal-parser/src/db_pool.py` | Added | +383 |
| `services/journal-parser/src/dependencies.py` | Added | +106 |
| `services/journal-parser/src/gap_detector.py` | Deleted | -183 |
| `services/journal-parser/src/generalized_extraction.py` | Added | +1,099 |
| `services/journal-parser/src/kafka_handler.py` | Modified | +67/-39 |
| `services/journal-parser/src/main.py` | Modified | +70/-155 |
| `services/journal-parser/src/orchestrator.py` | Added | +328 |
| `services/journal-parser/src/preprocessing.py` | Added | +497 |
| `services/journal-parser/src/quality_scoring.py` | Added | +327 |
| `services/journal-parser/src/storage_service.py` | Added | +911 |
| `services/journal-parser/src/worker.py` | Added | +405 |
| `services/journal-parser/tests/__init__.py` | Added | +4 |
| `services/journal-parser/tests/test_extraction.py` | Added | +388 |
| `shared/kafka/__init__.py` | Modified | +11/-4 |
| `shared/kafka/consumer.py` | Modified | +107 |
| `shared/kafka/producer.py` | Modified | +69 |
| `shared/kafka/topics.py` | Modified | +52/-22 |
| `shared/models/__init__.py` | Modified | +76 |
| `shared/models/extraction.py` | Added | +332 |
| `shared/models/patterns.py` | Added | +364 |

---

## Appendix B: Database Entity Relationship

```
                    +---------------+
                    |   categories  |
                    +---------------+
                          |
          +---------------+---------------+
          |                               |
    +-------------+                 +-------------+
    |activity_type|                 |metric_types |
    +-------------+                 +-------------+
          |                               |
    +-------------+                       |
    |activity_alia|                       |
    +-------------+                       |
          |                               |
          +---------------+---------------+
                          |
                          v
                 +------------------+
                 |journal_extraction|
                 +------------------+
                          |
    +----------+----------+----------+----------+----------+----------+
    |          |          |          |          |          |          |
    v          v          v          v          v          v          v
+-------+ +--------+ +---------+ +-------+ +-------+ +-------+ +------+
|metrics| |activiti| |consumpti| |social | | notes | | sleep | | gaps |
+-------+ +--------+ +---------+ +-------+ +-------+ +-------+ +------+
               |           |
               v           v
         +----------+ +----------+
         |activity_ | | food_    |
         |types     | | items    |
         +----------+ +----------+
```

---

## Appendix C: Gemini Prompt Structure

The extraction uses structured prompts to Gemini:

```
You are an intelligent journal analyzer for PLOS (Personal Life Operating System).

CONTEXT:
- User baseline: sleep_hours=7.5, mood_score=7.0, energy=6.5
- Recent patterns: exercises 3x/week, usually high energy on weekdays
- Current relationship state: HARMONY (5 days)

JOURNAL ENTRY:
"{user's journal text}"

EXTRACT:
1. Sleep (hours, quality 1-10, bedtime, waketime)
2. Metrics (mood 1-10, energy 1-10, stress 1-10, productivity 1-10)
3. Activities (name, category, duration, time_of_day, intensity)
4. Consumptions (name, type, meal_type, quantity, time_of_day)
5. Social (person, relationship, interaction_type, sentiment)
6. Notes (type: goal/gratitude/symptom/thought, content)

For each field:
- Mark as EXPLICIT if directly mentioned
- Mark as INFERRED if derived from context
- Include confidence (0-1)
- If ambiguous, add to gaps with clarification question

RESPOND IN JSON FORMAT.
```

---

*Report generated: December 30, 2025*
*PLOS Journal Processing v2.0*
