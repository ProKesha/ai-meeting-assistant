from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.meetings import router as meetings_router

app = FastAPI(title="AI Meeting & Task Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(meetings_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
