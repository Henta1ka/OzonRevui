"""Launch FastAPI app with ngrok tunnel for sharing"""
import os
import sys
import logging
from pyngrok import ngrok
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set ngrok auth token (if needed - optional for basic usage)
# ngrok.set_auth_token("YOUR_NGROK_AUTH_TOKEN")

def main():
    # Get port from env or use default
    port = int(os.getenv("PORT", 8000))
    
    # Start ngrok tunnel
    logger.info(f"Starting ngrok tunnel on port {port}...")
    try:
        public_url = ngrok.connect(port, "http")
        logger.info(f"\n\n{'='*80}")
        logger.info(f"🌐 PUBLIC URL: {public_url}")
        logger.info(f"{'='*80}\n")
        logger.info("Share this URL with your customer!")
        logger.info("Local URL: http://localhost:8000\n")
    except Exception as e:
        logger.error(f"Failed to start ngrok: {e}")
        logger.info("Make sure you have ngrok installed or download from https://ngrok.com")
        sys.exit(1)
    
    # Start FastAPI server
    logger.info("Starting FastAPI server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )

if __name__ == "__main__":
    main()
