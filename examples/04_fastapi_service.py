"""
A minimal identification web service with FastAPI.

    pip install pysourceafis fastapi uvicorn python-multipart
    uvicorn examples.04_fastapi_service:app          # run from the repository root

    curl -F image=@finger.png "http://127.0.0.1:8000/enroll?key=alice"
    curl -F image=@probe.png  http://127.0.0.1:8000/identify

This is a demo: it has no authentication, keeps templates only in memory and
does not encrypt anything. A real service needs all three (see docs/guide.md).
"""

import asyncio

from fastapi import FastAPI, File, HTTPException, UploadFile

from pysourceafis import Fingerprint, Gallery, ImageError

THRESHOLD = 60.0  # calibrate for your sensor and gallery size
MAX_UPLOAD = 5 * 1024 * 1024

app = FastAPI(title="pysourceafis demo")
gallery = Gallery()  # thread-safe; shared by all requests


async def read_fingerprint(image: UploadFile) -> Fingerprint:
    data = await image.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Image too large")
    try:
        # Extraction runs in Java without the GIL; keep the event loop free.
        return await asyncio.to_thread(Fingerprint.from_bytes, data)
    except ImageError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/enroll")
async def enroll(key: str, image: UploadFile = File(...)):
    fp = await read_fingerprint(image)
    if fp.minutiae_count < 12:
        raise HTTPException(422, "Too few features; capture the finger again")
    gallery.add(key, fp)
    return {"key": key, "minutiae": fp.minutiae_count, "gallery_size": len(gallery)}


@app.post("/identify")
async def identify(image: UploadFile = File(...), top_k: int = 5):
    probe = await read_fingerprint(image)
    hits = await asyncio.to_thread(gallery.search, probe, top_k)
    return {
        "match": bool(hits and hits[0].score >= THRESHOLD),
        "threshold": THRESHOLD,
        "candidates": [{"key": h.key, "score": round(h.score, 2)} for h in hits],
    }
