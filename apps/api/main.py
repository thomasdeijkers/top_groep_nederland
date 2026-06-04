from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from apps.dashboard.auth import auth_middleware, router as auth_router
from apps.dashboard.router import router as dashboard_router
from shared.db.connection import get_connection

app = FastAPI(title="Top Groep Nederland API")
app.middleware("http")(auth_middleware)

dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
app.mount(
    "/dashboard/static",
    StaticFiles(directory=dashboard_dir / "static"),
    name="dashboard-static",
)
app.include_router(auth_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {
        "status": "online",
        "app": "Top Groep Nederland API"
    }


@app.get("/test-db")
def test_db():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT NOW();")

    result = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "database_time": str(result[0]),
        "status": "database connected"
    }
