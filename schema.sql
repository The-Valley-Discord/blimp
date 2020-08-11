CREATE TABLE IF NOT EXISTS objects (
    oid INTEGER PRIMARY KEY,
    data STRING NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS aliases (
    gid INTEGER NOT NULL,
    alias STRING NOT NULL,
    oid INTEGER,
    FOREIGN KEY (oid) REFERENCES objects(oid),
    PRIMARY KEY (gid, alias)
);

CREATE TABLE IF NOT EXISTS rolekiosk_entries (
    oid INTEGER PRIMARY KEY,
    data STRING NOT NULL,
    FOREIGN KEY (oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS welcome_configuration (
    oid INTEGER PRIMARY KEY,
    join_data STRING,
    leave_data STRING,
    FOREIGN KEY (oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS board_configuration (
    oid INTEGER PRIMARY KEY,
    guild_oid INTEGER NOT NULL,
    data STRING NOT NULL,
    post_age_limit DATE,
    FOREIGN KEY (oid) REFERENCES objects(oid),
    FOREIGN KEY (guild_oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS board_entries (
    oid INTEGER PRIMARY KEY,
    original_oid INTEGER NOT NULL UNIQUE,
    FOREIGN KEY (oid) REFERENCES objects(oid),
    FOREIGN KEY (original_oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS reminders_entries (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message_oid INTEGER NOT NULL,
    due DATE NOT NULL,
    text STRING NOT NULL,
    FOREIGN KEY (message_oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS logging_configuration (
    guild_oid INTEGER PRIMARY KEY,
    channel_oid INTEGER,
    FOREIGN KEY (guild_oid) REFERENCES objects(oid),
    FOREIGN KEY (channel_oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS slowmode_configuration (
    channel_oid INTEGER PRIMARY KEY,
    secs UNSIGNED INTEGER NOT NULL,
    ignore_privileged_users BOOL NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid)
);

CREATE TABLE IF NOT EXISTS slowmode_entries (
    channel_oid INTEGER NOT NULL,
    user_oid INTEGER NOT NULL,
    timestamp DATE NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    FOREIGN KEY (user_oid) REFERENCES objects(oid),
    PRIMARY KEY (channel_oid, user_oid)
);