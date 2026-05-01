-- Multi-platform refactoring: per-platform settings, whitelist, and `platform`
-- column on existing tables (additive — backfilled with 'yahoo_finance').

-- ----------------------------------------------------------------------------
-- 1. Per-platform settings
-- ----------------------------------------------------------------------------
CREATE TABLE "platform_settings" (
    "id"                   SERIAL    PRIMARY KEY,
    "platform"             TEXT      NOT NULL UNIQUE,
    "display_name"         TEXT      NOT NULL,
    "enabled"              BOOLEAN   NOT NULL DEFAULT false,
    "mode"                 TEXT      NOT NULL DEFAULT 'test',
    "reply_enabled"        BOOLEAN   NOT NULL DEFAULT true,
    "post_enabled"         BOOLEAN   NOT NULL DEFAULT true,
    "ticker"               TEXT      NOT NULL DEFAULT 'VMAR',
    "max_replies_per_day"  INTEGER   NOT NULL DEFAULT 10,
    "max_posts_per_day"    INTEGER   NOT NULL DEFAULT 2,
    "min_post_length"      INTEGER   NOT NULL DEFAULT 20,
    "schedule_slots"       TEXT[]    NOT NULL DEFAULT ARRAY[]::TEXT[],
    "schedule_jitter_min"  INTEGER   NOT NULL DEFAULT 10,
    "reply_prompt"         TEXT,
    "post_prompt"          TEXT,
    "credentials"          JSONB,
    "config"               JSONB,
    "created_at"           TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"           TIMESTAMP(3) NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. Whitelist of authors the bot may reply to in test mode
-- ----------------------------------------------------------------------------
CREATE TABLE "whitelisted_authors" (
    "id"            BIGSERIAL PRIMARY KEY,
    "platform"      TEXT      NOT NULL,
    "author_handle" TEXT      NOT NULL,
    "note"          TEXT,
    "created_at"    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "whitelisted_authors_platform_author_key" UNIQUE ("platform", "author_handle")
);
CREATE INDEX "whitelisted_authors_platform_idx" ON "whitelisted_authors" ("platform");

-- ----------------------------------------------------------------------------
-- 3. Add `platform` column to existing tables (backfilled with 'yahoo_finance')
-- ----------------------------------------------------------------------------
ALTER TABLE "seen_comments"
    ADD COLUMN "platform" TEXT NOT NULL DEFAULT 'yahoo_finance';
CREATE INDEX "seen_comments_platform_idx"             ON "seen_comments" ("platform");
CREATE INDEX "seen_comments_platform_scraped_at_idx" ON "seen_comments" ("platform", "scraped_at");

ALTER TABLE "bot_activities"
    ADD COLUMN "platform" TEXT DEFAULT 'yahoo_finance';
CREATE INDEX "bot_activities_platform_created_at_idx" ON "bot_activities" ("platform", "created_at");

ALTER TABLE "bot_runs"
    ADD COLUMN "platform" TEXT NOT NULL DEFAULT 'yahoo_finance';
CREATE INDEX "bot_runs_platform_started_at_idx" ON "bot_runs" ("platform", "started_at");
