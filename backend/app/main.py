from fastapi import FastAPI

app = FastAPI(title="AI Knowledge Assistant API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
