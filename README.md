<p align="center">
  <img src="https://img.shields.io/badge/PLOS-Personal%20Life%20Management-blueviolet?style=for-the-badge" alt="PLOS"/>
</p>

<h1 align="center">PLOS - Personal Life Management System </h1>

<p align="center">
  <strong>An AI-powered platform that transforms your daily journal entries into structured life data, revealing patterns and insights about your habits, health, and happiness.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-brightgreen?style=flat-square" alt="Status"/>
  <img src="https://img.shields.io/badge/Phase-1%20Complete-blue?style=flat-square" alt="Phase"/>
  <img src="https://img.shields.io/badge/AI-Gemini%202.5-orange?style=flat-square" alt="AI"/>
  <img src="https://img.shields.io/badge/Backend-Python%20FastAPI-green?style=flat-square" alt="Backend"/>
</p>

---

## The Vision

**What if your daily journal entries could become a powerful database about your life?**

PLOS transforms the way you understand yourself. Write freely about your day - your sleep, workouts, meals, mood, work, relationships - and watch as AI extracts, organizes, and reveals patterns you never knew existed.

> *"I slept 7 hours, went for a morning run, had coffee with Sarah, worked on the API project for 4 hours, feeling pretty good today - maybe 8/10"*

This single sentence becomes **structured data** across 11 different life dimensions - sleep quality, exercise metrics, social connections, work productivity, and mood tracking - all searchable, analyzable, and ready to power personalized insights.

---

## What PLOS Does

### Turn Chaos Into Clarity

| You Write | PLOS Extracts |
|-----------|---------------|
| "Slept around 7 hours, woke up at 6am" | Sleep: 7h, Wake: 06:00, Bed: 23:00 |
| "45 min morning jog, felt great" | Exercise: Running, 45min, Morning, High Energy |
| "Had oatmeal and coffee for breakfast" | Nutrition: Oatmeal + Coffee, Breakfast, ~300 cal |
| "Mood is 8/10, productive day" | Mood: 8/10, Morning, High Confidence |
| "Lunch with Sarah at the Italian place" | Social: Sarah, Meal, Restaurant, Midday |
| "4 hours coding on the API project" | Work: Coding, 4h, API Project, Deep Focus |

### Discover Hidden Patterns

- **Sleep vs Mood Correlation**: See how your sleep quality affects next-day mood
- **Exercise Impact**: Track how workouts influence energy and productivity
- **Social Wellness**: Understand the relationship between social time and happiness
- **Work Patterns**: Identify your most productive hours and contexts
- **Nutrition Insights**: Connect eating habits with energy levels

### Build Your Personal Knowledge Base

Store everything - notes, ideas, articles, PDFs, links - and let AI retrieve exactly what you need, when you need it. Your second brain that actually remembers.

---

## Product Roadmap

<table>
<tr>
<td width="50%">

### Phase 1: Journal Intelligence
**Status: COMPLETE**

The foundation - AI-powered journal parsing that understands natural language and extracts structured life data.

**Delivered:**
- Natural language journal processing
- 11 extraction categories (sleep, mood, exercise, nutrition, work, social, health, activities, locations, weather, notes)
- Confidence scoring and quality assessment
- PostgreSQL storage with full history
- Real-time processing via Kafka events
- Prometheus metrics and monitoring

</td>
<td width="50%">

### Phase 2: Knowledge System
**Status: IN PROGRESS**

Your personal knowledge base - dump any information and retrieve it intelligently when needed.

**Building:**
- Vector embeddings for semantic search
- Document ingestion (PDFs, notes, links)
- Context-aware retrieval
- Knowledge graph connections
- "Ask your data" natural language queries

</td>
</tr>
<tr>
<td width="50%">

### Phase 3: Personal AI Assistant
**Status: PLANNED**

Your AI companion that knows you - personalized recommendations, goal tracking, daily briefings.

**Planned:**
- Daily personalized briefings
- Goal setting and progress tracking
- Smart task management
- Habit formation support
- Personalized insights and nudges
- Calendar integration

</td>
<td width="50%">

### Phase 4: Life Analytics Dashboard
**Status: PLANNED**

Visualize your life patterns with beautiful, insightful dashboards.

**Planned:**
- Interactive life metrics dashboard
- Time-series pattern visualization
- Correlation discovery engine
- Weekly/monthly life reports
- Trend predictions
- Comparative analytics

</td>
</tr>
</table>

---

## Progress Tracker

### Overall Completion: 35%

```
Phase 1: Journal Parsing     [####################] 100%
Phase 2: Knowledge System    [########............]  40%
Phase 3: AI Assistant        [....................]   0%
Phase 4: Life Analytics      [....................]   0%
```

### Detailed Status

| Component | Status | Description |
|-----------|--------|-------------|
| Journal Parser | Done | AI extraction for 11 life categories |
| Context Broker | Done | User state and context management |
| Knowledge System | In Progress | Vector search infrastructure ready |
| Semantic Search | In Progress | Qdrant integration complete |
| Document Ingestion | Planned | PDF, link, note processing |
| AI Assistant Core | Planned | Personalized recommendations engine |
| Goal Tracking | Planned | Goal setting and progress system |
| Task Management | Planned | Smart task prioritization |
| Analytics Dashboard | Planned | Life metrics visualization |
| Mobile App | Future | iOS/Android companion app |

---

## Current Capabilities

### Journal Processing (Live)

Process any journal entry and get structured data:

```
Input:  "Woke at 6am after 7.5h sleep. 45min morning run. 
         Oatmeal breakfast. 5h coding at work. Lunch with 
         Sarah. Mood 8/10. Weight 74.5kg."

Output:
  Sleep:      7.5 hours, wake 06:00, quality: good
  Exercise:   Running, 45 min, morning, moderate intensity
  Nutrition:  Oatmeal (breakfast), Lunch (social meal)
  Work:       Coding, 5 hours, deep focus session
  Social:     Sarah, meal together, midday
  Mood:       8/10, morning assessment
  Health:     Weight 74.5kg
  Activities: 4 distinct activities tracked
```

### Extraction Categories

| Category | What It Captures |
|----------|-----------------|
| Sleep | Duration, quality, wake/bed times, naps |
| Mood | Score, time of day, context, confidence |
| Exercise | Type, duration, intensity, calories |
| Nutrition | Meals, items, calories, timing |
| Work | Tasks, duration, projects, focus level |
| Social | People, interaction type, context |
| Health | Vitals, symptoms, medications |
| Activities | Any tracked activity with metadata |
| Locations | Places visited with context |
| Weather | Conditions affecting the day |
| Notes | Free-form observations and thoughts |

---

## Technical Excellence

### Built for Scale and Privacy

- **Your Data, Your Control**: Self-hosted, no cloud dependencies for personal data
- **AI-Powered**: Google Gemini 2.5 for intelligent extraction
- **Real-Time Processing**: Kafka event streaming for instant updates
- **Semantic Search**: Qdrant vector database for meaning-based retrieval
- **Production Ready**: Docker containerized, health monitored, metrics collected

### System Architecture

```
User Journal Entry
        |
        v
   [API Gateway] --> Authentication and Rate Limiting
        |
        v
  [Journal Parser] --> Gemini AI Extraction
        |
        v
    [Kafka Bus] --> Event Streaming
        |
   ______|______
  |      |      |
  v      v      v
[DB]  [Cache] [Vectors]
PostgreSQL  Redis  Qdrant
```

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| AI Engine | Google Gemini 2.5 | Natural language understanding |
| API Layer | FastAPI + Kong | REST APIs with gateway |
| Database | PostgreSQL | Structured life data storage |
| Cache | Redis | Fast data access |
| Vectors | Qdrant | Semantic search |
| Events | Apache Kafka | Real-time processing |
| Monitoring | Prometheus + Grafana | Observability |

---

## Why PLOS?

### The Problem

- Journals stay unstructured and unsearchable
- Life patterns remain hidden in plain text
- Personal knowledge is scattered everywhere
- No AI assistant truly knows YOU
- Generic apps don't understand your context

### The Solution

PLOS creates a **personal data layer** that:

1. **Understands** natural language about your life
2. **Extracts** structured data from unstructured text
3. **Stores** everything in a queryable format
4. **Connects** patterns across time and categories
5. **Retrieves** knowledge when you need it
6. **Assists** with personalized, context-aware AI

---

## Remaining Work

### High Priority
- [ ] Complete knowledge base document ingestion
- [ ] Build "Ask your data" query interface
- [ ] Implement daily summary generation
- [ ] Add goal tracking system
- [ ] Create life analytics dashboard

### Medium Priority
- [ ] Multi-modal input (voice, images)
- [ ] Calendar and task integration
- [ ] Habit tracking and streaks
- [ ] Weekly insight reports
- [ ] Relationship mapping

### Future Vision
- [ ] Mobile companion app
- [ ] Wearable device integration
- [ ] Predictive wellness alerts
- [ ] AI coaching conversations
- [ ] Export and portability tools

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Google Gemini API key

### Launch

```bash
# Clone the repository
git clone https://github.com/Sathish111j/PLOS-backend.git
cd PLOS-backend

# Configure environment
cp .env.example .env
# Add your GEMINI_API_KEYS to .env

# Start everything
docker compose up -d

# Verify all services are healthy
docker compose ps
```

### Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Journal API | http://localhost:8002 | Process journal entries |
| Knowledge API | http://localhost:8003 | Search and retrieve |
| Context API | http://localhost:8001 | User state management |
| Metabase | http://localhost:8082 | Data visualization & BI |
| Monitoring | http://localhost:9090 | Prometheus metrics |
| Dashboards | http://localhost:3333 | Grafana visualization |

---

## The Future

PLOS aims to become the **operating system for your personal life** - a unified platform where:

- Every thought, note, and journal entry becomes structured data
- AI understands your patterns better than you do
- Personalized insights help you live better
- Your second brain is always available
- Privacy is guaranteed through self-hosting

**This is not just an app. It's your personal life infrastructure.**

---

<p align="center">
  <strong>Built with purpose. Designed for privacy. Powered by AI.</strong>
</p>

<p align="center">
  <sub>Last Updated: December 31, 2025</sub>
</p>
