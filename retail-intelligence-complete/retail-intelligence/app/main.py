from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config.settings import DASHBOARD_DIR

app = FastAPI(
    title="Edge AI Retail Intelligence Platform",
    description="Edge-first on-device retail intelligence platform with shopper analytics, shelf inventory monitoring, queue intelligence, and Supabase cloud synchronization.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")

@app.get("/")
def root():
    return FileResponse(str(DASHBOARD_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
