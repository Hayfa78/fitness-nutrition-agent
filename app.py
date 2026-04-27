import os
import uvicorn
from localstorage_app.api_server import run_server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("FITAI_PORT", 8504)))
    print(f"FitAI API starting on port {port}")
    uvicorn.run(
        "localstorage_app.api_server:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
