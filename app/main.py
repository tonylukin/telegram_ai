from fastapi import FastAPI
from app.routers import all_routers

app = FastAPI()
for r in all_routers:
    app.include_router(r)

@app.get("/")
async def root():
    return {"message": "Hello World"}
