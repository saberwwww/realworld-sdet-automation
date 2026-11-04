"""Small read-only SQLite inspector, bound to the managed test environment."""
from contextlib import closing
import sqlite3

ARTICLE_SELECT = """
SELECT a.id, a.slug, a.title, a.summary, a.content, a.author_id,
       a.created, a.updated, u.username AS author_username
FROM articles_article AS a
LEFT JOIN accounts_user AS u ON u.id = a.author_id
"""


class ArticleDatabase:
    def __init__(self, environment):
        self.path = environment.database
        self.observations = []

    def _query(self, sql, parameters):
        # mode=ro refuses missing files instead of accidentally creating an empty DB.
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True,
                                     timeout=5, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(sql, parameters)]
        self.observations.append({"sql": sql.strip(), "parameters": list(parameters), "rows": rows})
        return rows

    def by_slug(self, slug):
        rows = self._query(ARTICLE_SELECT + " WHERE a.slug = ?", (slug,))
        assert len(rows) <= 1, "slug must identify at most one article"
        return rows[0] if rows else None

    def by_id(self, article_id):
        rows = self._query(ARTICLE_SELECT + " WHERE a.id = ?", (article_id,))
        assert len(rows) <= 1
        return rows[0] if rows else None

    def for_author(self, username):
        return self._query(ARTICLE_SELECT + " WHERE u.username = ? ORDER BY a.id", (username,))

    def count_for_author(self, username):
        return self._query("""SELECT COUNT(*) AS total FROM articles_article AS a
            JOIN accounts_user AS u ON u.id = a.author_id WHERE u.username = ?""", (username,))[0]["total"]


def assert_stored_article(row, payload, slug, username):
    assert row is not None, "API article has no persisted database row"
    assert row["slug"] == slug
    assert row["author_username"] == username
    assert row["title"] == payload["title"]
    assert row["summary"] == payload["description"]
    assert row["content"] == payload["body"]
