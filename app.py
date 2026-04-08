"""
app.py — Root entry point.
CMD: python app.py  (matches Dockerfile)
"""
import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=7860,
        log_level="info",
        access_log=True,
    )
