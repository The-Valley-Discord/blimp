import json
import sqlite3
from typing import Tuple


class BlimpObjects:
    """
    Internal "object" manager for Blimp. Powers aliasing.
    """

    def __init__(self, database: sqlite3.Connection):
        self.database = database

    def by_alias(self, guild_id: int, alias: str) -> Tuple[int, dict]:
        """Get (oid, data) or None behind an alias for the specified guild."""
        alias = self.database.execute(
            "SELECT * FROM aliases WHERE gid=:gid AND alias=:alias",
            {"gid": guild_id, "alias": alias},
        ).fetchone()
        if not alias:
            return None

        return (alias["oid"], self.by_oid(alias["oid"]))

    def by_data(self, **kwargs) -> int:
        """
        Find an object and return its oid or None.
        """
        obj = self.database.execute(
            "SELECT * FROM objects WHERE data=json(:data)", {"data": json.dumps(kwargs)}
        ).fetchone()
        if not obj:
            return None

        return obj["oid"]

    def by_oid(self, oid: int) -> dict:
        """
        Find an object's data or None by oid.
        """
        obj = self.database.execute(
            "SELECT * FROM objects WHERE oid=:oid", {"oid": oid}
        ).fetchone()
        if not obj:
            return None

        return json.loads(obj["data"])

    def make_object(self, **kwargs) -> int:
        """
        INSERT OR IGNORE an object and return its oid.
        """
        old = self.by_data(**kwargs)
        if old:
            return old

        cursor = self.database.execute(
            "INSERT INTO objects(data) VALUES(json(:data))",
            {"data": json.dumps(kwargs)},
        )
        return cursor.lastrowid
