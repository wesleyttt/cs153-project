import os
from dotenv import load_dotenv
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def load_secrets_from_file(filename="secrets.txt"):
    """Load API keys and other secrets from a file"""
    secrets = {}
    try:
        with open(filename, 'r') as file:
            for line in file:
                line = line.strip()
                if line and '=' in line:
                    # Handle line numbers if present (like in your file)
                    if '|' in line:
                        line = line.split('|', 1)[1]
                    
                    key, value = line.split('=', 1)
                    secrets[key.strip()] = value.strip()
        logger.info(f"Loaded secrets from {filename}")
        return secrets
    except Exception as e:
        logger.error(f"Error loading secrets from {filename}: {e}")
        return {}

# Load secrets from file
secrets = load_secrets_from_file()

# API Keys - prioritize env vars but fall back to secrets.txt
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY") or secrets.get("ELEVENLABS_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY") or secrets.get("MISTRAL_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or secrets.get("DISCORD_TOKEN")

# Default ElevenLabs voice ID
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "9BWtsMINqrJLrRacOk9x")

# API URLs
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Verify API keys are loaded
if not DISCORD_TOKEN:
    logger.error("ERROR: DISCORD_TOKEN not found in environment or secrets.txt")
    sys.exit(1)
    
if not ELEVENLABS_API_KEY:
    logger.warning("WARNING: ELEVENLABS_API_KEY not found - speech features will not work")

if not MISTRAL_API_KEY:
    logger.warning("WARNING: MISTRAL_API_KEY not found - translation features will not work") 