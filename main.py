from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth_routes import auth_router
from database import init_db
from order_routes import api_router, order_router

STATIC_DIR = Path(__file__).with_name("static")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Fisher — Controle financeiro",
    description=(
        "Aplicação pessoal de controle financeiro com transações persistentes, "
        "resumo mensal e metas."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(order_router)
app.include_router(api_router)
app.include_router(auth_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")
