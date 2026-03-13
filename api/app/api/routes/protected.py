from fastapi import APIRouter, Depends

from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal

router = APIRouter(dependencies=[Depends(require_authenticated_user)])


@router.get("/admin/overview")
def admin_overview(
    current_user: SessionPrincipal = Depends(require_platform_roles("ADMIN", "AUDITOR")),
) -> dict[str, object]:
    return {
        "status": "OK",
        "surface": "admin",
        "current_user_id": current_user.user_id,
        "platform_roles": list(current_user.platform_roles),
    }


@router.get("/api/meta")
def metadata(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
) -> dict[str, object]:
    return {
        "service": "api",
        "status": "AUTHENTICATED",
        "actor": {
            "id": current_user.user_id,
            "sub": current_user.oidc_sub,
            "platform_roles": list(current_user.platform_roles),
        },
        "boundaries": [
            "Deny-by-default protected routes",
            "Session-token enforcement with revocation",
            "Internal-only model execution posture",
        ],
    }
