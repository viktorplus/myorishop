"""FastAPI application entry point: static mount + routers."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import home, ops, products

app = FastAPI(title="MyOriShop")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(home.router)
app.include_router(ops.router)
app.include_router(products.router)
