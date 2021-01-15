-- schema update 2020-12-13
-- add a column to ticket categories to determine if we DM the transcript to all added users
ALTER TABLE ticket_categories ADD COLUMN dm_transcript BOOLEAN NOT NULL DEFAULT FALSE;
