from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PlatformRole = Literal["ADMIN", "AUDITOR"]
AuthMethod = Literal["dev", "oidc"]
AuthSource = Literal["bearer", "cookie"]


@dataclass(frozen=True)
class UserRecord:
    id: str
    oidc_sub: str
    email: str
    display_name: str
    last_login_at: datetime
    platform_roles: tuple[PlatformRole, ...]


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: str
    auth_method: AuthMethod
    issued_at: datetime
    expires_at: datetime
    csrf_token: str


@dataclass(frozen=True)
class SessionPrincipal:
    session_id: str
    auth_source: AuthSource
    user_id: str
    oidc_sub: str
    email: str
    display_name: str
    platform_roles: tuple[PlatformRole, ...]
    issued_at: datetime
    expires_at: datetime
    csrf_token: str
