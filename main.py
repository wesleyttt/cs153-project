import logging
from bot import TranslatorBot
from utils import load_opus
from config import DISCORD_TOKEN

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the bot"""
    # Load Opus for voice support
    load_opus()
    
    # Create and run the bot
    bot = TranslatorBot()
    
    logger.info("Starting bot...")
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main() 