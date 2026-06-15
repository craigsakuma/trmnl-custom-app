"""FastAPI application entrypoint.

v1 scaffold: exposes a health check so the service is runnable and deployable.
The slot engine and `/trmnl` polling endpoint are added in TCA-2.
"""

from fastapi import FastAPI

app = FastAPI(title="TRMNL Custom App")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
