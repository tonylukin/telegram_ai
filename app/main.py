from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import API_TOKEN, ENV
from app.configs.logger import logger
from app.routers import all_routers

app = FastAPI()
for r in all_routers:
    app.include_router(r)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth for open endpoints if needed
    if request.url.path in ["/open", "/docs", "/openapi.json"] or ENV == 'dev':
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(status_code=401, content={"detail": "Authorization header missing"})

    if auth_header != f"Bearer {API_TOKEN}":
        return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    return await call_next(request)

@app.get("/")
async def root():
    logger.info("Root endpoint was accessed")
    return {"message": "Hello World"}
