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