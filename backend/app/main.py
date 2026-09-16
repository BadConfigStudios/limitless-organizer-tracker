from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin as admin_router
from app.api.routers import auth as auth_router
from app.api.routers import organizers as organizers_router
from app.api.routers import status as status_router
from app.api.routers import tasks as tasks_router
from app.config import settings


def parse_cors_origins(value: str) -> list[str]:
    """Parse a comma-separated list of origins, trimming surrounding whitespace."""
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(title="Limitless Organizer Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)
app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(status_router.router)
app.include_router(organizers_router.router)
app.include_router(tasks_router.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
