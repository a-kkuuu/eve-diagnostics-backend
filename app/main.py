from fastapi import FastAPI

app = FastAPI(title="EVE Diagnostics Backend")

@app.get("/health")
def health_check():
    return {"status": "ok"}
