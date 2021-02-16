-- schema update 2021-02-16
-- add a table for board-excluded channels
CREATE TABLE board_exclusions (
    channel_oid INTEGER PRIMARY KEY,
    guild_oid INTEGER NOT NULL,
    FOREIGN KEY (channel_oid) REFERENCES objects(oid),
    FOREIGN KEY (channel_oid) REFERENCES objects(oid)
);
