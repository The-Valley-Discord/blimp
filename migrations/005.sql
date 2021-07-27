-- schema update 2021-07-08
-- unbreak various tables that use "string" instead of "text" for user input

CREATE TABLE new_reminders_entries (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message_oid INTEGER NOT NULL,
    due DATE NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY (message_oid) REFERENCES objects(oid)
);
INSERT INTO new_reminders_entries SELECT * FROM reminders_entries;
DROP TABLE reminders_entries;
ALTER TABLE new_reminders_entries RENAME TO reminders_entries;

CREATE TABLE new_channelban_entries (
    channel_oid INTEGER NOT NULL,
    guild_oid INTEGER NOT NULL,
    user_oid INTEGER NOT NULL,
    issuer_oid INTEGER NOT NULL,
    issued_at DATE DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    FOREIGN KEY (guild_oid) REFERENCES objects(oid),
    FOREIGN KEY (user_oid) REFERENCES objects(oid),
    FOREIGN KEY (issuer_oid) REFERENCES objects(oid),
    PRIMARY KEY (channel_oid, user_oid)
);
INSERT INTO new_channelban_entries SELECT * FROM channelban_entries;
DROP TABLE channelban_entries;
ALTER TABLE new_channelban_entries RENAME TO channelban_entries;

CREATE TABLE new_ticket_classes (
    category_oid INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    FOREIGN KEY (category_oid) REFERENCES objects(oid),
    PRIMARY KEY (category_oid, name)
);
INSERT INTO new_ticket_classes SELECT * FROM ticket_classes;
DROP TABLE ticket_classes;
ALTER TABLE new_ticket_classes RENAME TO ticket_classes;

CREATE TABLE new_trigger_entries (
    message_oid INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    command TEXT NOT NULL,

    FOREIGN KEY (message_oid) REFERENCES objects(oid),
    PRIMARY KEY (message_oid, emoji)
);
INSERT INTO new_trigger_entries SELECT * FROM trigger_entries;
DROP TABLE trigger_entries;
ALTER TABLE new_trigger_entries RENAME TO trigger_entries;

CREATE TABLE new_post_entries (
    message_oid INTEGER NOT NULL,
    text TEXT NOT NULL,

    FOREIGN KEY (message_oid) REFERENCES objects(oid),
    PRIMARY KEY (message_oid)
);
INSERT INTO new_post_entries SELECT * FROM post_entries;
DROP TABLE post_entries;
ALTER TABLE new_post_entries RENAME TO post_entries;
