-- Initialize pgvector extension and minimal schema for AI 面试平台

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  name text,
  year integer,
  major text,
  created_at timestamptz DEFAULT now()
);



CREATE TABLE IF NOT EXISTS jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text,
  requirements jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text,
  body text,
  type text,
  difficulty integer DEFAULT 1,
  meta jsonb
);

CREATE TABLE IF NOT EXISTS interviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  job_id uuid REFERENCES jobs(id),
  started_at timestamptz DEFAULT now(),
  ended_at timestamptz,
  status text DEFAULT 'created'
);

CREATE TABLE IF NOT EXISTS interview_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interview_id uuid REFERENCES interviews(id) ON DELETE CASCADE,
  question_id uuid REFERENCES questions(id),
  "order" integer,
  candidate_answer text,
  score numeric,
  feedback text
);

CREATE TABLE IF NOT EXISTS interview_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interview_id uuid REFERENCES interviews(id) ON DELETE CASCADE,
  sender text NOT NULL,            -- 'candidate' | 'ai' | 'interviewer' | 'system'
  role text,
  content text NOT NULL,
  parsed_json jsonb,
  embedding vector(1536),
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interview_rounds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interview_id uuid REFERENCES interviews(id) ON DELETE CASCADE,
  round_index integer NOT NULL,
  question_id uuid NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interview_id uuid REFERENCES interviews(id) ON DELETE CASCADE,
  generated_at timestamptz DEFAULT now(),
  status text DEFAULT 'pending',
  report_json jsonb,
  embedding vector(1536)
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  token_hash text UNIQUE NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_resumes (
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  text_content text,
  summary text,
  keywords jsonb,
  file_name text,
  file_path text,
  updated_at timestamptz DEFAULT now()
);

-- pgcrypto for gen_random_uuid if not present
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Question bank linking questions to jobs (job-specific banks)
CREATE TABLE IF NOT EXISTS job_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid REFERENCES jobs(id) ON DELETE CASCADE,
  question_id uuid REFERENCES questions(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now()
);

-- Attempts: stores practice/test sessions and results
CREATE TABLE IF NOT EXISTS attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  job_id uuid REFERENCES jobs(id),
  mode text NOT NULL, -- 'practice' | 'test'
  duration_seconds integer DEFAULT 0,
  question_count integer DEFAULT 0,
  score numeric,
  started_at timestamptz DEFAULT now(),
  ended_at timestamptz,
  metadata jsonb
);

CREATE TABLE IF NOT EXISTS attempt_answers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  attempt_id uuid REFERENCES attempts(id) ON DELETE CASCADE,
  question_id uuid REFERENCES questions(id),
  answer_text text,
  is_correct boolean,
  score numeric,
  time_spent_seconds integer DEFAULT 0,
  submitted_at timestamptz DEFAULT now()
);

