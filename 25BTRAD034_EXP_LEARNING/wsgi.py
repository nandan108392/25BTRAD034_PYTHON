import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

# Import the core Flask application instance
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
