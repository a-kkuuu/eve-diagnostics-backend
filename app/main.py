from fastapi import FastAPI
from app.routers import auth, centres, tests_catalogue, bookings, payments

app = FastAPI(title="EVE Diagnostics Backend")

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests_catalogue.router)
app.include_router(bookings.router)
app.include_router(payments.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
