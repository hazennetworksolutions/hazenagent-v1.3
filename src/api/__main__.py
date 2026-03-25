"""Entry point for running the API server with python -m src.api."""
import uvicorn
from src.api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

