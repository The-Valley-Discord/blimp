CREATE TABLE applied_migrations (
    number INTEGER PRIMARY KEY
);

CREATE TABLE objects (
    oid INTEGER PRIMARY KEY,
    data STRING NOT NULL UNIQUE
);

CREATE TABLE aliases (
    gid INTEGER NOT NULL,
    alias STRING NOT NULL,
    oid INTEGER,
    FOREIGN KEY (oid) REFERENCES objects(oid),
    PRIMARY KEY (gid, alias)
);

CREATE TABLE rolekiosk_entries (
    oid INTEGER PRIMARY KEY,
    data STRING NOT NULL,
    FOREIGN KEY (oid) REFERENCES objects(oid)
);

CREATE TABLE welcome_configuration (
    oid INTEGER PRIMARY KEY,
    join_data STRING,
    leave_data STRING,
    FOREIGN KEY (oid) REFERENCES objects(oid)
);

CREATE TABLE board_configuration (
    oid INTEGER PRIMARY KEY,
    guild_oid INTEGER NOT NULL,
    data STRING NOT NULL,
    post_age_limit DATE,
    FOREIGN KEY (oid) REFERENCES objects(oid),
    FOREIGN KEY (guild_oid) REFERENCES objects(oid)
);

CREATE TABLE board_entries (
    oid INTEGER PRIMARY KEY,
    original_oid INTEGER NOT NULL UNIQUE,
    FOREIGN KEY (oid) REFERENCES objects(oid),
    FOREIGN KEY (original_oid) REFERENCES objects(oid)
);

CREATE TABLE reminders_entries (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message_oid INTEGER NOT NULL,
    due DATE NOT NULL,
    text STRING NOT NULL,
    FOREIGN KEY (message_oid) REFERENCES objects(oid)
);

CREATE TABLE logging_configuration (
    guild_oid INTEGER PRIMARY KEY,
    channel_oid INTEGER,
    FOREIGN KEY (guild_oid) REFERENCES objects(oid),
    FOREIGN KEY (channel_oid) REFERENCES objects(oid)
);

CREATE TABLE slowmode_configuration (
    channel_oid INTEGER PRIMARY KEY,
    secs UNSIGNED INTEGER NOT NULL,
    ignore_privileged_users BOOL NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid)
);

CREATE TABLE slowmode_entries (
    channel_oid INTEGER NOT NULL,
    user_oid INTEGER NOT NULL,
    timestamp DATE NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    FOREIGN KEY (user_oid) REFERENCES objects(oid),
    PRIMARY KEY (channel_oid, user_oid)
);

CREATE TABLE channelban_entries (
    channel_oid INTEGER NOT NULL,
    guild_oid INTEGER NOT NULL,
    user_oid INTEGER NOT NULL,
    issuer_oid INTEGER NOT NULL,
    issued_at DATE DEFAULT CURRENT_TIMESTAMP,
    reason STRING NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    FOREIGN KEY (guild_oid) REFERENCES objects(oid),
    FOREIGN KEY (user_oid) REFERENCES objects(oid),
    FOREIGN KEY (issuer_oid) REFERENCES objects(oid),
    PRIMARY KEY (channel_oid, user_oid)
);

CREATE TABLE ticket_categories (
    category_oid INTEGER PRIMARY KEY,
    guild_oid INTEGER NOT NULL,
    count INTEGER NOT NULL,
    transcript_channel_oid INTEGER NOT NULL,
    per_user_limit INTEGER,
    can_creator_close BOOL NOT NULL,

    FOREIGN KEY (category_oid) REFERENCES objects(oid),
    FOREIGN KEY (guild_oid) REFERENCES objects(oid),
    FOREIGN KEY (transcript_channel_oid) REFERENCES objects(oid)
);

CREATE TABLE ticket_classes (
    category_oid INTEGER NOT NULL,
    name STRING NOT NULL,
    description STRING,

    FOREIGN KEY (category_oid) REFERENCES objects(oid),
    PRIMARY KEY (category_oid, name)
);

CREATE TABLE ticket_entries (
    channel_oid INTEGER PRIMARY KEY,
    category_oid INTEGER NOT NULL,
    creator_id INTEGER NOT NULL,
    open BOOLEAN NOT NULL,

    FOREIGN KEY (category_oid) REFERENCES objects(oid),
    FOREIGN KEY (channel_oid) REFERENCES objects(oid)
);

CREATE TABLE ticket_participants (
    channel_oid INTEGER NOT NULL,
    user_id INTEGER NOT NULL,

    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    PRIMARY KEY (channel_oid, user_id)
);

CREATE TABLE trigger_entries (
    message_oid INTEGER NOT NULL,
    emoji STRING NOT NULL,
    command STRING NOT NULL,

    FOREIGN KEY (message_oid) REFERENCES objects(oid),
    PRIMARY KEY (message_oid, emoji)
);

CREATE TABLE post_entries (
    message_oid INTEGER NOT NULL,
    text STRING NOT NULL,

    FOREIGN KEY (message_oid) REFERENCES objects(oid),
    PRIMARY KEY (message_oid)
);

