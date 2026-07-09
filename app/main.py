"""FastAPI application entry point: static mount + routers."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import dictionary, home, ops, products, receipts

app = FastAPI(title="MyOriShop")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(home.router)
app.include_router(ops.router)
app.include_router(products.router)
app.include_router(dictionary.router)
app.include_router(receipts.router)
