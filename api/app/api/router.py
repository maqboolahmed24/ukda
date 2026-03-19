from fastapi import APIRouter

from app.api.routes.audit import admin_router as audit_admin_router
from app.api.routes.audit import me_router as audit_me_router
from app.api.routes.auth import protected_router as auth_protected_router
from app.api.routes.auth import public_router as auth_public_router
from app.api.routes.capacity import router as capacity_router
from app.api.routes.documents import router as documents_router
from app.api.routes.exports import internal_router as exports_internal_router
from app.api.routes.exports import router as exports_router
from app.api.routes.indexes import admin_router as indexes_admin_router
from app.api.routes.indexes import router as indexes_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.launch import router as launch_router
from app.api.routes.model_assignments import router as model_assignments_router
from app.api.routes.operations import router as operations_router
from app.api.routes.policies import router as policies_router
from app.api.routes.projects import router as projects_router
from app.api.routes.protected import router as protected_router
from app.api.routes.pseudonym_registry import router as pseudonym_registry_router
from app.api.routes.recovery import router as recovery_router
from app.api.routes.security import router as security_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_public_router)
api_router.include_router(auth_protected_router)
api_router.include_router(audit_admin_router)
api_router.include_router(audit_me_router)
api_router.include_router(launch_router)
api_router.include_router(operations_router)
api_router.include_router(capacity_router)
api_router.include_router(recovery_router)
api_router.include_router(security_router)
api_router.include_router(projects_router)
api_router.include_router(policies_router)
api_router.include_router(pseudonym_registry_router)
api_router.include_router(model_assignments_router)
api_router.include_router(documents_router)
api_router.include_router(exports_router)
api_router.include_router(exports_internal_router)
api_router.include_router(jobs_router)
api_router.include_router(indexes_admin_router)
api_router.include_router(indexes_router)
api_router.include_router(protected_router)
