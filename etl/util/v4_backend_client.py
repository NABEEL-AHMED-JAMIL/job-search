"""
    v4_backend Postgres Client
    @author: Nabeel Ahmed Jamil

    Thin wrapper around the v4_backend database (a separate Postgres instance/DB
    from process's own etl_job) for the F768920 user-import step -- inserts into
    app_user / app_user_preference / app_user_tenant / app_user_role using that
    schema directly, since there's no REST API in front of it yet.
"""
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)


class V4BackendClient:

    def __init__(self, host=None, port=None, database=None, user=None, password=None):
        self.host = host or os.getenv("V4_BACKEND_HOST", "localhost")
        self.port = port or os.getenv("V4_BACKEND_PORT", "5432")
        self.database = database or os.getenv("V4_BACKEND_DB", "v4_backend")
        self.user = user or os.getenv("V4_BACKEND_USER", "nabeel.amd93")
        self.password = password or os.getenv("V4_BACKEND_PASSWORD", "admin")
        self._conn = None

    def connect(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self.host, port=self.port, dbname=self.database,
                user=self.user, password=self.password
            )
        return self._conn

    def close(self):
        if self._conn is not None and not self._conn.closed:
            self._conn.close()

    def fetch_all(self, query, params=None):
        conn = self.connect()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def fetch_one(self, query, params=None):
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None

    def execute(self, query, params=None):
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()

    def role_id_by_code(self):
        """ {role_code: role_id} for every row in app_role. """
        rows = self.fetch_all("SELECT id, code FROM app_role")
        return {row["code"]: row["id"] for row in rows}

    def find_user_id_by_email(self, email):
        row = self.fetch_one("SELECT id FROM app_user WHERE email = %s", (email,))
        return row["id"] if row else None

    def default_tenant_id(self):
        """ There's only ever been one tenant seeded so far -- use it as the default. """
        row = self.fetch_one("SELECT id FROM app_tenant ORDER BY created_at ASC LIMIT 1")
        return row["id"] if row else None
