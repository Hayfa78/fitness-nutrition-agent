"""FitAI backend launcher for the React website."""

import os

import uvicorn
from localstorage_app.api_server import app

port = int(os.environ.get("PORT", 8504))

if __name__ == "__main__":
    print(f"FitAI API starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
