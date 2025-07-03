from fastapi import FastAPI

from app.configs.logger import logger
from app.routers import all_routers

app = FastAPI()
for r in all_routers:
    app.include_router(r)

@app.get("/")
async def root():
    logger.info("Root endpoint was accessed")
    return {"message": "Hello World"}
