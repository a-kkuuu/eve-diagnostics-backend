from fastapi import FastAPI
from app.routers import auth, centres, tests_catalogue

app = FastAPI(title="EVE Diagnostics Backend")

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests_catalogue.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
