from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
from psycopg.rows import dict_row

from app.auth.models import (
    AuthMethod,
    AuthSource,
    PlatformRole,
    SessionPrincipal,
    SessionRecord,
    UserRecord,
)
from app.core.config import Settings

AUTH_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      oidc_sub TEXT NOT NULL UNIQUE,
      email TEXT NOT NULL,
      display_name TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_login_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_platform_roles (
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK (role IN ('ADMIN', 'AUDITOR')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (user_id, role)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      auth_method TEXT NOT NULL CHECK (auth_method IN ('dev', 'oidc')),
      issued_at TIMESTAMPTZ NOT NULL,
      expires_at TIMESTAMPTZ NOT NULL,
      csrf_token TEXT NOT NULL,
      revoked_at TIMESTAMPTZ
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)
    """,
)


class AuthStoreUnavailableError(RuntimeError):
    """Auth persistence could not be reached."""


class AuthStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._schema_initialized = False

    @staticmethod
    def _as_conninfo(database_url: str) -> str:
        if database_url.startswith("postgresql+psycopg://"):
            return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return database_url

    def _connect(self) -> psycopg.Connection:
        conninfo = self._as_conninfo(self._settings.database_url)
        return psycopg.connect(conninfo=conninfo, connect_timeout=2)

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in AUTH_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                    self._seed_dev_users(cursor=cursor)
                connection.commit()
        except psycopg.Error as error:
            raise AuthStoreUnavailableError("Auth schema could not be initialized.") from error

        self._schema_initialized = True

    def _seed_dev_users(self, *, cursor: psycopg.Cursor) -> None:
        if not self._settings.auth_dev_mode_enabled:
            return

        now = datetime.now(UTC)
        for seed in self._settings.auth_dev_seed_users:
            stable_id = str(uuid5(NAMESPACE_URL, f"ukde-dev-seed:{seed.oidc_sub}"))
            cursor.execute(
                """
                INSERT INTO users (
                  id,
                  oidc_sub,
                  email,
                  display_name,
                  created_at,
                  last_login_at
                )
                VALUES (
                  %(id)s,
                  %(oidc_sub)s,
                  %(email)s,
                  %(display_name)s,
                  %(created_at)s,
                  %(last_login_at)s
                )
                ON CONFLICT (oidc_sub) DO UPDATE
                SET
                  email = EXCLUDED.email,
                  display_name = EXCLUDED.display_name
                """,
                {
                    "id": stable_id,
                    "oidc_sub": seed.oidc_sub,
                    "email": seed.email,
                    "display_name": seed.display_name,
                    "created_at": now,
                    "last_login_at": now,
                },
            )

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE oidc_sub = %(oidc_sub)s
                """,
                {"oidc_sub": seed.oidc_sub},
            )
            row = cursor.fetchone()
            if row is None:
                continue
            user_id = row[0]
            cursor.execute(
                """
                DELETE FROM user_platform_roles
                WHERE user_id = %(user_id)s
                """,
                {"user_id": user_id},
            )
            for role in seed.platform_roles:
                cursor.execute(
                    """
                    INSERT INTO user_platform_roles (user_id, role)
                    VALUES (%(user_id)s, %(role)s)
                    ON CONFLICT (user_id, role) DO NOTHING
                    """,
                    {
                        "user_id": user_id,
                        "role": role,
                    },
                )

    @staticmethod
    def _normalize_roles(roles: list[str]) -> tuple[PlatformRole, ...]:
        ordered: list[PlatformRole] = []
        for role in roles:
            if role not in {"ADMIN", "AUDITOR"}:
                continue
            if role in ordered:
                continue
            ordered.append(role)  # type: ignore[arg-type]
        return tuple(ordered)

    def _load_user(
        self,
        *,
        cursor: psycopg.Cursor,
        user_id: str,
    ) -> UserRecord | None:
        cursor.execute(
            """
            SELECT
              u.id,
              u.oidc_sub,
              u.email,
              u.display_name,
              u.last_login_at,
              COALESCE(
                ARRAY_AGG(r.role) FILTER (WHERE r.role IS NOT NULL),
                ARRAY[]::TEXT[]
              ) AS platform_roles
            FROM users AS u
            LEFT JOIN user_platform_roles AS r
              ON r.user_id = u.id
            WHERE u.id = %(user_id)s
            GROUP BY u.id, u.oidc_sub, u.email, u.display_name, u.last_login_at
            """,
            {"user_id": user_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return UserRecord(
            id=row["id"],
            oidc_sub=row["oidc_sub"],
            email=row["email"],
            display_name=row["display_name"],
            last_login_at=row["last_login_at"],
            platform_roles=self._normalize_roles(row["platform_roles"]),
        )

    def upsert_user(
        self,
        *,
        oidc_sub: str,
        email: str,
        display_name: str,
        platform_roles: tuple[PlatformRole, ...],
    ) -> UserRecord:
        self.ensure_schema()
        now = datetime.now(UTC)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM users
                        WHERE oidc_sub = %(oidc_sub)s
                        """,
                        {"oidc_sub": oidc_sub},
                    )
                    existing = cursor.fetchone()

                    if existing is None:
                        user_id = str(uuid4())
                        cursor.execute(
                            """
                            INSERT INTO users (
                              id,
                              oidc_sub,
                              email,
                              display_name,
                              created_at,
                              last_login_at
                            )
                            VALUES (
                              %(id)s,
                              %(oidc_sub)s,
                              %(email)s,
                              %(display_name)s,
                              %(created_at)s,
                              %(last_login_at)s
                            )
                            """,
                            {
                                "id": user_id,
                                "oidc_sub": oidc_sub,
                                "email": email,
                                "display_name": display_name,
                                "created_at": now,
                                "last_login_at": now,
                            },
                        )
                    else:
                        user_id = existing["id"]
                        cursor.execute(
                            """
                            UPDATE users
                            SET
                              email = %(email)s,
                              display_name = %(display_name)s,
                              last_login_at = %(last_login_at)s
                            WHERE id = %(id)s
                            """,
                            {
                                "id": user_id,
                                "email": email,
                                "display_name": display_name,
                                "last_login_at": now,
                            },
                        )

                    cursor.execute(
                        """
                        DELETE FROM user_platform_roles
                        WHERE user_id = %(user_id)s
                        """,
                        {"user_id": user_id},
                    )
                    for role in platform_roles:
                        cursor.execute(
                            """
                            INSERT INTO user_platform_roles (user_id, role)
                            VALUES (%(user_id)s, %(role)s)
                            ON CONFLICT (user_id, role) DO NOTHING
                            """,
                            {
                                "user_id": user_id,
                                "role": role,
                            },
                        )

                    user = self._load_user(cursor=cursor, user_id=user_id)
                    if user is None:
                        raise AuthStoreUnavailableError("Failed to load user after upsert.")
                connection.commit()
        except psycopg.Error as error:
            raise AuthStoreUnavailableError("User upsert failed.") from error

        return user

    def create_session(
        self,
        *,
        user_id: str,
        auth_method: AuthMethod,
        ttl_seconds: int,
    ) -> SessionRecord:
        self.ensure_schema()
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        session_id = str(uuid4())
        csrf_token = str(uuid4())

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO sessions (
                          id,
                          user_id,
                          auth_method,
                          issued_at,
                          expires_at,
                          csrf_token
                        )
                        VALUES (
                          %(id)s,
                          %(user_id)s,
                          %(auth_method)s,
                          %(issued_at)s,
                          %(expires_at)s,
                          %(csrf_token)s
                        )
                        """,
                        {
                            "id": session_id,
                            "user_id": user_id,
                            "auth_method": auth_method,
                            "issued_at": issued_at,
                            "expires_at": expires_at,
                            "csrf_token": csrf_token,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise AuthStoreUnavailableError("Session creation failed.") from error

        return SessionRecord(
            id=session_id,
            user_id=user_id,
            auth_method=auth_method,
            issued_at=issued_at,
            expires_at=expires_at,
            csrf_token=csrf_token,
        )

    def get_session_principal(
        self,
        *,
        session_id: str,
        auth_source: AuthSource,
    ) -> SessionPrincipal | None:
        self.ensure_schema()

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          s.id AS session_id,
                          s.issued_at,
                          s.expires_at,
                          s.revoked_at,
                          s.csrf_token,
                          u.id AS user_id,
                          u.oidc_sub,
                          u.email,
                          u.display_name,
                          COALESCE(
                            ARRAY_AGG(r.role) FILTER (WHERE r.role IS NOT NULL),
                            ARRAY[]::TEXT[]
                          ) AS platform_roles
                        FROM sessions AS s
                        INNER JOIN users AS u
                          ON u.id = s.user_id
                        LEFT JOIN user_platform_roles AS r
                          ON r.user_id = u.id
                        WHERE s.id = %(session_id)s
                        GROUP BY
                          s.id,
                          s.issued_at,
                          s.expires_at,
                          s.revoked_at,
                          s.csrf_token,
                          u.id,
                          u.oidc_sub,
                          u.email,
                          u.display_name
                        """,
                        {"session_id": session_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise AuthStoreUnavailableError("Session lookup failed.") from error

        if row is None:
            return None
        if row["revoked_at"] is not None:
            return None
        if row["expires_at"] <= datetime.now(UTC):
            return None

        return SessionPrincipal(
            session_id=row["session_id"],
            auth_source=auth_source,
            user_id=row["user_id"],
            oidc_sub=row["oidc_sub"],
            email=row["email"],
            display_name=row["display_name"],
            platform_roles=self._normalize_roles(row["platform_roles"]),
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            csrf_token=row["csrf_token"],
        )

    def revoke_session(self, *, session_id: str) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE sessions
                        SET revoked_at = NOW()
                        WHERE id = %(session_id)s
                        """,
                        {"session_id": session_id},
                    )
                connection.commit()
        except psycopg.Error as error:
            raise AuthStoreUnavailableError("Session revocation failed.") from error
