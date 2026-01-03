--
-- PostgreSQL database dump
--

-- Dumped from database version 15.8
-- Dumped by pg_dump version 15.8

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


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: extraction_activities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_activities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    extraction_id uuid NOT NULL,
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
    activity_subcategory character varying(50),
    CONSTRAINT extraction_activities_intensity_check CHECK (((intensity)::text = ANY (ARRAY[('low'::character varying)::text, ('medium'::character varying)::text, ('high'::character varying)::text]))),
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
    CONSTRAINT extraction_consumptions_consumption_type_check CHECK (((consumption_type)::text = ANY (ARRAY[('meal'::character varying)::text, ('snack'::character varying)::text, ('drink'::character varying)::text, ('medication'::character varying)::text, ('supplement'::character varying)::text]))),
    CONSTRAINT extraction_consumptions_meal_type_check CHECK (((meal_type)::text = ANY (ARRAY[('breakfast'::character varying)::text, ('lunch'::character varying)::text, ('dinner'::character varying)::text, ('snack'::character varying)::text])))
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
    CONSTRAINT extraction_social_sentiment_check CHECK (((sentiment)::text = ANY (ARRAY[('positive'::character varying)::text, ('negative'::character varying)::text, ('neutral'::character varying)::text, ('conflict'::character varying)::text])))
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
-- Name: metric_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_types ALTER COLUMN id SET DEFAULT nextval('public.metric_types_id_seq'::regclass);


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
-- Name: journal_extractions journal_extractions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.journal_extractions
    ADD CONSTRAINT journal_extractions_pkey PRIMARY KEY (id);


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
-- Name: idx_activities_cat_subcat; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_cat_subcat ON public.extraction_activities USING btree (activity_category, activity_subcategory);


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
-- Name: idx_activities_subcategory; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_subcategory ON public.extraction_activities USING btree (activity_subcategory);


--
-- Name: idx_activities_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_time ON public.extraction_activities USING btree (time_of_day);


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
-- Name: user_context_state user_context_state_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_context_state
    ADD CONSTRAINT user_context_state_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

