from fastapi import FastAPI


app = FastAPI(title="TraceGuard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
