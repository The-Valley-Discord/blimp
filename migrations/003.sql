-- schema update 2021-02-08
-- add a table for SIG membership
CREATE TABLE sig_entries (
    channel_oid INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    PRIMARY KEY (channel_oid, user_id)
);