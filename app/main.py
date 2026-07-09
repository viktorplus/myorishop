"""FastAPI application entry point: lifespan backup + static mount + routers."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import (
    backup,
    customers,
    dictionary,
    home,
    ops,
    products,
    receipts,
    sales,
    writeoffs,
)

# Module-qualified import: tests monkeypatch backup_service.startup_backup
# as ONE seam (PD-13).
from app.services import backup as backup_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # D-09: snapshot the DB BEFORE serving requests; the sync call is
    # intentional — startup must block until the backup finishes.
    backup_service.startup_backup()
    yield


app = FastAPI(title="MyOriShop", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(home.router)
app.include_router(ops.router)
app.include_router(products.router)
app.include_router(dictionary.router)
app.include_router(receipts.router)
app.include_router(sales.router)
app.include_router(customers.router)
app.include_router(backup.router)
app.include_router(writeoffs.router)
