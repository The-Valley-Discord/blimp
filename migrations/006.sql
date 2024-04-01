-- schema update 2024-03-31
-- wow, it's been a while, old man
-- add coop rep tables

CREATE TABLE coop_descriptions (
	thread_id INTEGER PRIMARY KEY,
	server_id INTEGER,
	name TEXT,
	description TEXT
);

CREATE TABLE coop_reps (
	user_id INTEGER,
	thread_id INTEGER,
	PRIMARY KEY (user_id, thread_id)
);

CREATE TABLE coop_subscribers (
	user_id INTEGER,
	thread_id INTEGER,
	PRIMARY KEY (user_id, thread_id)
);

CREATE TABLE coop_bans (
	user_id INTEGER,
	thread_id INTEGER,
	rep_id INTEGER NOT NULL,
	reason TEXT NOT NULL,
	expires DATETIME,
	PRIMARY KEY (user_id, thread_id)
);
