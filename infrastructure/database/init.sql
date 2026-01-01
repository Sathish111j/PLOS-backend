--
-- PostgreSQL database dump
--

-- Dumped from database version 15.15
-- Dumped by pg_dump version 15.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: data_gap_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.data_gap_status AS ENUM (
    'pending',
    'answered',
    'skipped',
    'expired'
);


--
-- Name: extraction_quality; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.extraction_quality AS ENUM (
    'high',
    'medium',
    'low'
);


--
-- Name: time_of_day; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.time_of_day AS ENUM (
    'early_morning',
    'morning',
    'afternoon',
    'evening',
    'night',
    'late_night'
);


--
-- Name: calculate_user_baseline(uuid, date, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_user_baseline(p_user_id uuid, p_entry_date date, p_days integer DEFAULT 30) RETURNS TABLE(avg_sleep double precision, stddev_sleep double precision, avg_mood double precision, stddev_mood double precision, avg_energy double precision, stddev_energy double precision, avg_stress double precision, stddev_stress double precision, sample_count bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        AVG(CASE WHEN mt.name = 'sleep_duration' THEN em.value END)::FLOAT as avg_sleep,
        STDDEV(CASE WHEN mt.name = 'sleep_duration' THEN em.value END)::FLOAT as stddev_sleep,
        AVG(CASE WHEN mt.name = 'mood_score' THEN em.value END)::FLOAT as avg_mood,
        STDDEV(CASE WHEN mt.name = 'mood_score' THEN em.value END)::FLOAT as stddev_mood,
        AVG(CASE WHEN mt.name = 'energy_level' THEN em.value END)::FLOAT as avg_energy,
        STDDEV(CASE WHEN mt.name = 'energy_level' THEN em.value END)::FLOAT as stddev_energy,
        AVG(CASE WHEN mt.name = 'stress_level' THEN em.value END)::FLOAT as avg_stress,
        STDDEV(CASE WHEN mt.name = 'stress_level' THEN em.value END)::FLOAT as stddev_stress,
        COUNT(DISTINCT je.id)::BIGINT as sample_count
    FROM journal_extractions je
    JOIN extraction_metrics em ON je.id = em.extraction_id
    JOIN metric_types mt ON em.metric_type_id = mt.id
    WHERE je.user_id = p_user_id
      AND je.entry_date >= (p_entry_date - p_days)
      AND je.entry_date < p_entry_date;
END;
$$;


--
-- Name: FUNCTION calculate_user_baseline(p_user_id uuid, p_entry_date date, p_days integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.calculate_user_baseline(p_user_id uuid, p_entry_date date, p_days integer) IS 'Calculates user baseline metrics from journal extractions.';


--
-- Name: get_activity_totals(uuid, date, date, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_activity_totals(p_user_id uuid, p_start_date date, p_end_date date, p_category character varying DEFAULT NULL::character varying) RETURNS TABLE(activity character varying, category character varying, total_minutes bigint, total_hours double precision, occurrences bigint, avg_satisfaction double precision, total_calories bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.activity::VARCHAR,
        v.category::VARCHAR,
        SUM(v.duration_minutes)::BIGINT,
        SUM(v.duration_minutes)::FLOAT / 60,
        COUNT(*)::BIGINT,
        AVG(v.satisfaction)::FLOAT,
        SUM(v.calories_burned)::BIGINT
    FROM v_activity_summary v
    WHERE v.user_id = p_user_id
      AND v.entry_date BETWEEN p_start_date AND p_end_date
      AND (p_category IS NULL OR v.category = p_category)
    GROUP BY v.activity, v.category
    ORDER BY SUM(v.duration_minutes) DESC NULLS LAST;
END;
$$;


--
-- Name: resolve_activity_name(character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resolve_activity_name(p_name character varying) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_type_id INT;
BEGIN
    -- Try exact match first
    SELECT id INTO v_type_id FROM activity_types 
    WHERE canonical_name = LOWER(p_name) OR display_name ILIKE p_name;
    
    IF v_type_id IS NOT NULL THEN
        RETURN v_type_id;
    END IF;
    
    -- Try alias
    SELECT activity_type_id INTO v_type_id FROM activity_aliases
    WHERE alias ILIKE p_name OR alias ILIKE '%' || p_name || '%';
    
    IF v_type_id IS NOT NULL THEN
        RETURN v_type_id;
    END IF;
    
    -- Try fuzzy match
    SELECT at.id INTO v_type_id FROM activity_types at
    WHERE at.canonical_name % LOWER(p_name)  -- trigram similarity
    ORDER BY similarity(at.canonical_name, LOWER(p_name)) DESC
    LIMIT 1;
    
    RETURN v_type_id;  -- May be NULL
END;
$$;


--
-- Name: FUNCTION resolve_activity_name(p_name character varying); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.resolve_activity_name(p_name character varying) IS 'Resolves user activity text to canonical activity_type_id using exact match, alias, then fuzzy match.';


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: update_user_pattern_cache(uuid, character varying, double precision, double precision, integer, integer, jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_user_pattern_cache(p_user_id uuid, p_pattern_type character varying, p_value double precision, p_std_dev double precision, p_sample_count integer, p_day_of_week integer DEFAULT NULL::integer, p_metadata jsonb DEFAULT '{}'::jsonb) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_pattern_id UUID;
BEGIN
    INSERT INTO user_patterns (
        user_id, pattern_type, day_of_week, value, std_dev, 
        sample_count, confidence, metadata, last_updated
    ) VALUES (
        p_user_id, p_pattern_type, p_day_of_week, p_value, p_std_dev,
        p_sample_count, 
        LEAST(p_sample_count::FLOAT / 30.0, 1.0),  -- Confidence based on samples
        p_metadata,
        NOW()
    )
    ON CONFLICT (user_id, pattern_type, day_of_week) 
    DO UPDATE SET
        value = EXCLUDED.value,
        std_dev = EXCLUDED.std_dev,
        sample_count = EXCLUDED.sample_count,
        confidence = LEAST(EXCLUDED.sample_count::FLOAT / 30.0, 1.0),
        metadata = EXCLUDED.metadata,
        last_updated = NOW()
    RETURNING id INTO v_pattern_id;
    
    RETURN v_pattern_id;
END;
$$;


--
-- Name: FUNCTION update_user_pattern_cache(p_user_id uuid, p_pattern_type character varying, p_value double precision, p_std_dev double precision, p_sample_count integer, p_day_of_week integer, p_metadata jsonb); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.update_user_pattern_cache(p_user_id uuid, p_pattern_type character varying, p_value double precision, p_std_dev double precision, p_sample_count integer, p_day_of_week integer, p_metadata jsonb) IS 'Upserts a user pattern into the cache.';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activity_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_aliases (
    id integer NOT NULL,
    alias character varying(100) NOT NULL,
    activity_type_id integer NOT NULL,
    confidence double precision DEFAULT 1.0,
    source character varying(50) DEFAULT 'manual'::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE activity_aliases; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.activity_aliases IS 'Maps user variations to canonical activity names. Grows over time as we learn new terms.';


--
-- Name: activity_aliases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_aliases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_aliases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_aliases_id_seq OWNED BY public.activity_aliases.id;


--
-- Name: activity_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_types (
    id integer NOT NULL,
    canonical_name character varying(100) NOT NULL,
    display_name character varying(100) NOT NULL,
    category_id integer NOT NULL,
    is_physical boolean DEFAULT false,
    is_screen_time boolean DEFAULT false,
    avg_calories_per_hour integer,
    typical_duration_minutes integer,
    search_vector tsvector,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE activity_types; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.activity_types IS 'Controlled vocabulary for activities. New activities are added here with canonical names.';


--
-- Name: activity_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_types_id_seq OWNED BY public.activity_types.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100) NOT NULL,
    parent_id integer,
    description text,
    icon character varying(50),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: extraction_activities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_activities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    activity_type_id integer,
    activity_raw character varying(100),
    start_time time without time zone,
    end_time time without time zone,
    duration_minutes integer,
    time_of_day public.time_of_day,
    intensity character varying(10),
    satisfaction integer,
    calories_burned integer,
    confidence double precision DEFAULT 0.5,
    raw_mention text,
    needs_clarification boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    activity_category character varying(50),
    is_outdoor boolean,
    with_others boolean,
    location character varying(100),
    mood_before integer,
    mood_after integer,
    CONSTRAINT extraction_activities_intensity_check CHECK (((intensity)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying])::text[]))),
    CONSTRAINT extraction_activities_mood_after_check CHECK (((mood_after >= 1) AND (mood_after <= 10))),
    CONSTRAINT extraction_activities_mood_before_check CHECK (((mood_before >= 1) AND (mood_before <= 10))),
    CONSTRAINT extraction_activities_satisfaction_check CHECK (((satisfaction >= 1) AND (satisfaction <= 10)))
);


--
-- Name: extraction_consumptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_consumptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    consumption_type character varying(20) NOT NULL,
    meal_type character varying(20),
    food_item_id integer,
    item_raw character varying(200),
    consumption_time time without time zone,
    time_of_day public.time_of_day,
    quantity double precision DEFAULT 1,
    unit character varying(20) DEFAULT 'serving'::character varying,
    calories integer,
    protein_g double precision,
    carbs_g double precision,
    fat_g double precision,
    is_healthy boolean,
    is_home_cooked boolean,
    confidence double precision DEFAULT 0.5,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now(),
    fiber_g double precision,
    sugar_g double precision,
    sodium_mg double precision,
    food_category character varying(50),
    caffeine_mg double precision,
    alcohol_units double precision,
    is_processed boolean,
    water_ml integer,
    CONSTRAINT extraction_consumptions_consumption_type_check CHECK (((consumption_type)::text = ANY ((ARRAY['meal'::character varying, 'snack'::character varying, 'drink'::character varying, 'medication'::character varying, 'supplement'::character varying])::text[]))),
    CONSTRAINT extraction_consumptions_meal_type_check CHECK (((meal_type)::text = ANY ((ARRAY['breakfast'::character varying, 'lunch'::character varying, 'dinner'::character varying, 'snack'::character varying])::text[])))
);


--
-- Name: extraction_gaps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_gaps (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    field_category character varying(50) NOT NULL,
    question text NOT NULL,
    context text,
    original_mention text,
    priority integer DEFAULT 1,
    status public.data_gap_status DEFAULT 'pending'::public.data_gap_status,
    user_response text,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE extraction_gaps; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.extraction_gaps IS 'Questions that need user clarification. LLM generates these when data is ambiguous.';


--
-- Name: extraction_health; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_health (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    symptom_type character varying(100) NOT NULL,
    body_part character varying(50),
    severity integer,
    duration_minutes integer,
    time_of_day character varying(20),
    possible_cause text,
    medication_taken text,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now(),
    is_resolved boolean,
    impact_score integer,
    triggers text,
    CONSTRAINT extraction_health_impact_score_check CHECK (((impact_score >= 1) AND (impact_score <= 10))),
    CONSTRAINT extraction_health_severity_check CHECK (((severity >= 1) AND (severity <= 10)))
);


--
-- Name: extraction_locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_locations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    location_name character varying(255) NOT NULL,
    location_type character varying(50),
    time_of_day character varying(20),
    duration_minutes integer,
    activity_context text,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: extraction_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_metrics (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    metric_type_id integer NOT NULL,
    value double precision NOT NULL,
    confidence double precision DEFAULT 0.5,
    time_of_day public.time_of_day,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: extraction_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_notes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    note_type character varying(50) NOT NULL,
    content text NOT NULL,
    sentiment character varying(20),
    confidence double precision DEFAULT 0.5,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: extraction_sleep; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_sleep (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    duration_hours double precision,
    quality integer,
    bedtime time without time zone,
    waketime time without time zone,
    disruptions integer DEFAULT 0,
    trouble_falling_asleep boolean,
    woke_up_tired boolean,
    nap_duration_minutes integer DEFAULT 0,
    confidence double precision DEFAULT 0.5,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now(),
    sleep_environment character varying(100),
    pre_sleep_activity character varying(100),
    dreams_noted text,
    CONSTRAINT extraction_sleep_quality_check CHECK (((quality >= 1) AND (quality <= 10)))
);


--
-- Name: extraction_social; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_social (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    person_name character varying(100),
    relationship character varying(50),
    interaction_type character varying(50),
    sentiment character varying(20),
    time_of_day public.time_of_day,
    duration_minutes integer,
    confidence double precision DEFAULT 0.5,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now(),
    quality_score integer,
    is_virtual boolean,
    topic character varying(200),
    relationship_category character varying(50),
    mood_before integer,
    mood_after integer,
    interaction_outcome character varying(50),
    conflict_level integer,
    emotional_impact character varying(50),
    initiated_by character varying(20),
    location character varying(100),
    CONSTRAINT extraction_social_conflict_level_check CHECK (((conflict_level >= 0) AND (conflict_level <= 10))),
    CONSTRAINT extraction_social_mood_after_check CHECK (((mood_after >= 1) AND (mood_after <= 10))),
    CONSTRAINT extraction_social_mood_before_check CHECK (((mood_before >= 1) AND (mood_before <= 10))),
    CONSTRAINT extraction_social_quality_score_check CHECK (((quality_score >= 1) AND (quality_score <= 10))),
    CONSTRAINT extraction_social_sentiment_check CHECK (((sentiment)::text = ANY ((ARRAY['positive'::character varying, 'negative'::character varying, 'neutral'::character varying, 'conflict'::character varying])::text[])))
);


--
-- Name: COLUMN extraction_social.relationship; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.relationship IS 'Specific: mom, dad, girlfriend, boyfriend, boss, colleague, classmate, teacher, student, neighbor, etc.';


--
-- Name: COLUMN extraction_social.relationship_category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.relationship_category IS 'family|romantic|professional|friend|acquaintance|other';


--
-- Name: COLUMN extraction_social.mood_before; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.mood_before IS 'Mood 1-10 before interaction';


--
-- Name: COLUMN extraction_social.mood_after; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.mood_after IS 'Mood 1-10 after interaction';


--
-- Name: COLUMN extraction_social.interaction_outcome; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.interaction_outcome IS 'resolved|ongoing|escalated|positive|negative|neutral';


--
-- Name: COLUMN extraction_social.conflict_level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.conflict_level IS '0=no conflict, 10=major fight';


--
-- Name: COLUMN extraction_social.emotional_impact; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.emotional_impact IS 'energized|drained|supported|stressed|happy|sad|frustrated|calm|anxious';


--
-- Name: COLUMN extraction_social.initiated_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.extraction_social.initiated_by IS 'user|other|mutual';


--
-- Name: extraction_weather; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_weather (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    weather_condition character varying(50),
    temperature_feel character varying(20),
    mentioned_impact text,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: extraction_work; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_work (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
    work_type character varying(50),
    project_name character varying(200),
    duration_minutes integer,
    time_of_day public.time_of_day,
    productivity_score integer,
    focus_quality character varying(20),
    interruptions integer DEFAULT 0,
    accomplishments text,
    blockers text,
    raw_mention text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT extraction_work_productivity_score_check CHECK (((productivity_score >= 1) AND (productivity_score <= 10)))
);


--
-- Name: food_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.food_aliases (
    id integer NOT NULL,
    alias character varying(100) NOT NULL,
    food_item_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: food_aliases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.food_aliases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: food_aliases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.food_aliases_id_seq OWNED BY public.food_aliases.id;


--
-- Name: food_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.food_items (
    id integer NOT NULL,
    canonical_name character varying(100) NOT NULL,
    display_name character varying(100) NOT NULL,
    category character varying(50),
    serving_size_g integer DEFAULT 100,
    calories_per_serving integer,
    protein_g double precision,
    carbs_g double precision,
    fat_g double precision,
    fiber_g double precision,
    is_healthy boolean,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: food_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.food_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: food_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.food_items_id_seq OWNED BY public.food_items.id;


--
-- Name: journal_extractions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.journal_extractions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    entry_date date NOT NULL,
    raw_entry text NOT NULL,
    preprocessed_entry text,
    overall_quality public.extraction_quality,
    extraction_time_ms integer,
    gemini_model character varying(50),
    has_gaps boolean DEFAULT false,
    gaps_resolved boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: metric_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metric_types (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100) NOT NULL,
    category_id integer,
    unit character varying(20),
    min_value double precision,
    max_value double precision,
    description text
);


--
-- Name: metric_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metric_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metric_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metric_types_id_seq OWNED BY public.metric_types.id;


--
-- Name: user_context_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_context_state (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid,
    current_mood_score integer,
    current_energy_level integer,
    current_stress_level integer,
    sleep_quality_avg_7d numeric(4,2),
    productivity_score_avg_7d numeric(4,2),
    active_goals_count integer DEFAULT 0,
    pending_tasks_count integer DEFAULT 0,
    completed_tasks_today integer DEFAULT 0,
    context_data jsonb,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE user_context_state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_context_state IS 'Real-time user context for fast API responses.';


--
-- Name: user_patterns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_patterns (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    pattern_type character varying(50) NOT NULL,
    day_of_week integer,
    value double precision,
    std_dev double precision,
    sample_count integer DEFAULT 0,
    confidence double precision DEFAULT 0.5,
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT user_patterns_confidence_check CHECK (((confidence >= (0)::double precision) AND (confidence <= (1)::double precision))),
    CONSTRAINT user_patterns_day_of_week_check CHECK (((day_of_week >= 0) AND (day_of_week <= 6)))
);


--
-- Name: TABLE user_patterns; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_patterns IS 'Cached user patterns and baselines for fast context retrieval. Updated periodically.';


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    timezone character varying(50) DEFAULT 'UTC'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp with time zone,
    is_active boolean DEFAULT true,
    is_verified boolean DEFAULT false
);


--
-- Name: v_activity_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_activity_summary AS
 SELECT je.user_id,
    je.entry_date,
    COALESCE(at.canonical_name, ea.activity_raw) AS activity,
    COALESCE(at.display_name, ea.activity_raw) AS activity_display,
    c.name AS category,
    ea.duration_minutes,
    ea.time_of_day,
    ea.intensity,
    ea.satisfaction,
    ea.calories_burned,
    at.is_physical,
    at.is_screen_time
   FROM (((public.extraction_activities ea
     JOIN public.journal_extractions je ON ((ea.extraction_id = je.id)))
     LEFT JOIN public.activity_types at ON ((ea.activity_type_id = at.id)))
     LEFT JOIN public.categories c ON ((at.category_id = c.id)));


--
-- Name: v_daily_nutrition; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_daily_nutrition AS
 SELECT je.user_id,
    je.entry_date,
    count(*) FILTER (WHERE ((ec.consumption_type)::text = 'meal'::text)) AS meals_count,
    sum(ec.calories) AS total_calories,
    sum(ec.protein_g) AS total_protein,
    sum(ec.carbs_g) AS total_carbs,
    sum(ec.fat_g) AS total_fat,
    count(*) FILTER (WHERE (ec.is_healthy = true)) AS healthy_items,
    count(*) FILTER (WHERE (ec.is_home_cooked = true)) AS home_cooked
   FROM (public.extraction_consumptions ec
     JOIN public.journal_extractions je ON ((ec.extraction_id = je.id)))
  GROUP BY je.user_id, je.entry_date;


--
-- Name: v_dow_mood_patterns; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_dow_mood_patterns AS
 SELECT je.user_id,
    EXTRACT(dow FROM je.entry_date) AS day_of_week,
    avg(em.value) AS avg_mood,
    stddev(em.value) AS stddev_mood,
    count(*) AS sample_count
   FROM ((public.journal_extractions je
     JOIN public.extraction_metrics em ON ((je.id = em.extraction_id)))
     JOIN public.metric_types mt ON ((em.metric_type_id = mt.id)))
  WHERE ((mt.name)::text = 'mood_score'::text)
  GROUP BY je.user_id, (EXTRACT(dow FROM je.entry_date));


--
-- Name: v_pending_gaps; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_pending_gaps AS
 SELECT je.user_id,
    eg.id AS gap_id,
    je.entry_date,
    eg.field_category,
    eg.question,
    eg.context,
    eg.priority,
    eg.created_at
   FROM (public.extraction_gaps eg
     JOIN public.journal_extractions je ON ((eg.extraction_id = je.id)))
  WHERE (eg.status = 'pending'::public.data_gap_status)
  ORDER BY eg.priority, eg.created_at;


--
-- Name: v_rolling_averages; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_rolling_averages AS
 SELECT je.user_id,
    je.entry_date,
    avg(em.value) FILTER (WHERE ((mt.name)::text = 'mood_score'::text)) OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_mood_7d,
    avg(em.value) FILTER (WHERE ((mt.name)::text = 'energy_level'::text)) OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_energy_7d,
    avg(em.value) FILTER (WHERE ((mt.name)::text = 'sleep_duration'::text)) OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_sleep_7d,
    avg(em.value) FILTER (WHERE ((mt.name)::text = 'stress_level'::text)) OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_stress_7d
   FROM ((public.journal_extractions je
     JOIN public.extraction_metrics em ON ((je.id = em.extraction_id)))
     JOIN public.metric_types mt ON ((em.metric_type_id = mt.id)));


--
-- Name: activity_aliases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_aliases ALTER COLUMN id SET DEFAULT nextval('public.activity_aliases_id_seq'::regclass);


--
-- Name: activity_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_types ALTER COLUMN id SET DEFAULT nextval('public.activity_types_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: food_aliases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_aliases ALTER COLUMN id SET DEFAULT nextval('public.food_aliases_id_seq'::regclass);


--
-- Name: food_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_items ALTER COLUMN id SET DEFAULT nextval('public.food_items_id_seq'::regclass);


--
-- Name: metric_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_types ALTER COLUMN id SET DEFAULT nextval('public.metric_types_id_seq'::regclass);


--
-- Name: activity_aliases activity_aliases_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_aliases
    ADD CONSTRAINT activity_aliases_alias_key UNIQUE (alias);


--
-- Name: activity_aliases activity_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_aliases
    ADD CONSTRAINT activity_aliases_pkey PRIMARY KEY (id);


--
-- Name: activity_types activity_types_canonical_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_types
    ADD CONSTRAINT activity_types_canonical_name_key UNIQUE (canonical_name);


--
-- Name: activity_types activity_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_types
    ADD CONSTRAINT activity_types_pkey PRIMARY KEY (id);


--
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: extraction_activities extraction_activities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_activities
    ADD CONSTRAINT extraction_activities_pkey PRIMARY KEY (id);


--
-- Name: extraction_consumptions extraction_consumptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_consumptions
    ADD CONSTRAINT extraction_consumptions_pkey PRIMARY KEY (id);


--
-- Name: extraction_gaps extraction_gaps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_gaps
    ADD CONSTRAINT extraction_gaps_pkey PRIMARY KEY (id);


--
-- Name: extraction_health extraction_health_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_health
    ADD CONSTRAINT extraction_health_pkey PRIMARY KEY (id);


--
-- Name: extraction_locations extraction_locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_locations
    ADD CONSTRAINT extraction_locations_pkey PRIMARY KEY (id);


--
-- Name: extraction_metrics extraction_metrics_extraction_id_metric_type_id_time_of_day_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_metrics
    ADD CONSTRAINT extraction_metrics_extraction_id_metric_type_id_time_of_day_key UNIQUE (extraction_id, metric_type_id, time_of_day);


--
-- Name: extraction_metrics extraction_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_metrics
    ADD CONSTRAINT extraction_metrics_pkey PRIMARY KEY (id);


--
-- Name: extraction_notes extraction_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_notes
    ADD CONSTRAINT extraction_notes_pkey PRIMARY KEY (id);


--
-- Name: extraction_sleep extraction_sleep_extraction_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_sleep
    ADD CONSTRAINT extraction_sleep_extraction_id_key UNIQUE (extraction_id);


--
-- Name: extraction_sleep extraction_sleep_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_sleep
    ADD CONSTRAINT extraction_sleep_pkey PRIMARY KEY (id);


--
-- Name: extraction_social extraction_social_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_social
    ADD CONSTRAINT extraction_social_pkey PRIMARY KEY (id);


--
-- Name: extraction_weather extraction_weather_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_weather
    ADD CONSTRAINT extraction_weather_pkey PRIMARY KEY (id);


--
-- Name: extraction_work extraction_work_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_work
    ADD CONSTRAINT extraction_work_pkey PRIMARY KEY (id);


--
-- Name: food_aliases food_aliases_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_aliases
    ADD CONSTRAINT food_aliases_alias_key UNIQUE (alias);


--
-- Name: food_aliases food_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_aliases
    ADD CONSTRAINT food_aliases_pkey PRIMARY KEY (id);


--
-- Name: food_items food_items_canonical_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_items
    ADD CONSTRAINT food_items_canonical_name_key UNIQUE (canonical_name);


--
-- Name: food_items food_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_items
    ADD CONSTRAINT food_items_pkey PRIMARY KEY (id);


--
-- Name: journal_extractions journal_extractions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.journal_extractions
    ADD CONSTRAINT journal_extractions_pkey PRIMARY KEY (id);


--
-- Name: journal_extractions journal_extractions_user_id_entry_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.journal_extractions
    ADD CONSTRAINT journal_extractions_user_id_entry_date_key UNIQUE (user_id, entry_date);


--
-- Name: metric_types metric_types_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_types
    ADD CONSTRAINT metric_types_name_key UNIQUE (name);


--
-- Name: metric_types metric_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_types
    ADD CONSTRAINT metric_types_pkey PRIMARY KEY (id);


--
-- Name: user_context_state user_context_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_context_state
    ADD CONSTRAINT user_context_state_pkey PRIMARY KEY (id);


--
-- Name: user_context_state user_context_state_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_context_state
    ADD CONSTRAINT user_context_state_user_id_key UNIQUE (user_id);


--
-- Name: user_patterns user_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_patterns
    ADD CONSTRAINT user_patterns_pkey PRIMARY KEY (id);


--
-- Name: user_patterns user_patterns_user_id_pattern_type_day_of_week_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_patterns
    ADD CONSTRAINT user_patterns_user_id_pattern_type_day_of_week_key UNIQUE (user_id, pattern_type, day_of_week);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_activities_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_category ON public.extraction_activities USING btree (activity_category);


--
-- Name: idx_activities_date_cat; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_date_cat ON public.extraction_activities USING btree (extraction_id, activity_category);


--
-- Name: idx_activities_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_extraction ON public.extraction_activities USING btree (extraction_id);


--
-- Name: idx_activities_raw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_raw ON public.extraction_activities USING btree (activity_raw);


--
-- Name: idx_activities_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_time ON public.extraction_activities USING btree (time_of_day);


--
-- Name: idx_activities_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_type ON public.extraction_activities USING btree (activity_type_id);


--
-- Name: idx_activity_types_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_types_category ON public.activity_types USING btree (category_id);


--
-- Name: idx_activity_types_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_types_search ON public.activity_types USING gin (search_vector);


--
-- Name: idx_aliases_alias; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aliases_alias ON public.activity_aliases USING btree (alias);


--
-- Name: idx_aliases_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aliases_trgm ON public.activity_aliases USING gin (alias public.gin_trgm_ops);


--
-- Name: idx_categories_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_name ON public.categories USING btree (name);


--
-- Name: idx_categories_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categories_parent ON public.categories USING btree (parent_id);


--
-- Name: idx_consumptions_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_category ON public.extraction_consumptions USING btree (food_category);


--
-- Name: idx_consumptions_date_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_date_type ON public.extraction_consumptions USING btree (extraction_id, food_category);


--
-- Name: idx_consumptions_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_extraction ON public.extraction_consumptions USING btree (extraction_id);


--
-- Name: idx_consumptions_meal_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_meal_type ON public.extraction_consumptions USING btree (meal_type);


--
-- Name: idx_consumptions_raw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_raw ON public.extraction_consumptions USING btree (item_raw);


--
-- Name: idx_consumptions_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_time ON public.extraction_consumptions USING btree (time_of_day);


--
-- Name: idx_consumptions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consumptions_type ON public.extraction_consumptions USING btree (consumption_type);


--
-- Name: idx_extractions_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_extractions_user_date ON public.journal_extractions USING btree (user_id, entry_date);


--
-- Name: idx_food_items_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_food_items_category ON public.food_items USING btree (category);


--
-- Name: idx_gaps_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gaps_extraction ON public.extraction_gaps USING btree (extraction_id);


--
-- Name: idx_gaps_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gaps_status ON public.extraction_gaps USING btree (status);


--
-- Name: idx_health_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_health_extraction ON public.extraction_health USING btree (extraction_id);


--
-- Name: idx_health_symptom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_health_symptom ON public.extraction_health USING btree (symptom_type);


--
-- Name: idx_journal_entry_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_journal_entry_date ON public.journal_extractions USING btree (entry_date);


--
-- Name: idx_journal_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_journal_user_date ON public.journal_extractions USING btree (user_id, entry_date);


--
-- Name: idx_journal_user_entry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_journal_user_entry ON public.journal_extractions USING btree (user_id, entry_date);


--
-- Name: idx_locations_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_locations_extraction ON public.extraction_locations USING btree (extraction_id);


--
-- Name: idx_locations_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_locations_type ON public.extraction_locations USING btree (location_type);


--
-- Name: idx_metrics_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_extraction ON public.extraction_metrics USING btree (extraction_id);


--
-- Name: idx_metrics_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_type ON public.extraction_metrics USING btree (metric_type_id);


--
-- Name: idx_notes_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notes_extraction ON public.extraction_notes USING btree (extraction_id);


--
-- Name: idx_notes_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notes_type ON public.extraction_notes USING btree (note_type);


--
-- Name: idx_social_conflict; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_conflict ON public.extraction_social USING btree (conflict_level);


--
-- Name: idx_social_emotional_impact; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_emotional_impact ON public.extraction_social USING btree (emotional_impact);


--
-- Name: idx_social_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_extraction ON public.extraction_social USING btree (extraction_id);


--
-- Name: idx_social_person; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_person ON public.extraction_social USING btree (person_name);


--
-- Name: idx_social_relationship; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_relationship ON public.extraction_social USING btree (relationship);


--
-- Name: idx_social_relationship_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_relationship_category ON public.extraction_social USING btree (relationship_category);


--
-- Name: idx_social_sentiment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_social_sentiment ON public.extraction_social USING btree (sentiment);


--
-- Name: idx_user_patterns_dow; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_patterns_dow ON public.user_patterns USING btree (day_of_week);


--
-- Name: idx_user_patterns_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_patterns_type ON public.user_patterns USING btree (pattern_type);


--
-- Name: idx_user_patterns_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_patterns_user ON public.user_patterns USING btree (user_id);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: idx_weather_condition; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weather_condition ON public.extraction_weather USING btree (weather_condition);


--
-- Name: idx_weather_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weather_extraction ON public.extraction_weather USING btree (extraction_id);


--
-- Name: idx_work_extraction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_extraction ON public.extraction_work USING btree (extraction_id);


--
-- Name: idx_work_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_work_type ON public.extraction_work USING btree (work_type);


--
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: activity_aliases activity_aliases_activity_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_aliases
    ADD CONSTRAINT activity_aliases_activity_type_id_fkey FOREIGN KEY (activity_type_id) REFERENCES public.activity_types(id);


--
-- Name: activity_types activity_types_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_types
    ADD CONSTRAINT activity_types_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: categories categories_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.categories(id);


--
-- Name: extraction_activities extraction_activities_activity_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_activities
    ADD CONSTRAINT extraction_activities_activity_type_id_fkey FOREIGN KEY (activity_type_id) REFERENCES public.activity_types(id);


--
-- Name: extraction_activities extraction_activities_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_activities
    ADD CONSTRAINT extraction_activities_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_consumptions extraction_consumptions_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_consumptions
    ADD CONSTRAINT extraction_consumptions_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_consumptions extraction_consumptions_food_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_consumptions
    ADD CONSTRAINT extraction_consumptions_food_item_id_fkey FOREIGN KEY (food_item_id) REFERENCES public.food_items(id);


--
-- Name: extraction_gaps extraction_gaps_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_gaps
    ADD CONSTRAINT extraction_gaps_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_health extraction_health_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_health
    ADD CONSTRAINT extraction_health_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_locations extraction_locations_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_locations
    ADD CONSTRAINT extraction_locations_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_metrics extraction_metrics_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_metrics
    ADD CONSTRAINT extraction_metrics_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_metrics extraction_metrics_metric_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_metrics
    ADD CONSTRAINT extraction_metrics_metric_type_id_fkey FOREIGN KEY (metric_type_id) REFERENCES public.metric_types(id);


--
-- Name: extraction_notes extraction_notes_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_notes
    ADD CONSTRAINT extraction_notes_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_sleep extraction_sleep_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_sleep
    ADD CONSTRAINT extraction_sleep_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_social extraction_social_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_social
    ADD CONSTRAINT extraction_social_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_weather extraction_weather_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_weather
    ADD CONSTRAINT extraction_weather_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: extraction_work extraction_work_extraction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_work
    ADD CONSTRAINT extraction_work_extraction_id_fkey FOREIGN KEY (extraction_id) REFERENCES public.journal_extractions(id) ON DELETE CASCADE;


--
-- Name: food_aliases food_aliases_food_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.food_aliases
    ADD CONSTRAINT food_aliases_food_item_id_fkey FOREIGN KEY (food_item_id) REFERENCES public.food_items(id);


--
-- Name: metric_types metric_types_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_types
    ADD CONSTRAINT metric_types_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: user_context_state user_context_state_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_context_state
    ADD CONSTRAINT user_context_state_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

