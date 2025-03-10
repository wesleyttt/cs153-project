import discord
import logging

logger = logging.getLogger(__name__)

def load_opus():
    """Load Opus library for voice support"""
    if not discord.opus.is_loaded():
        try:
            # For Apple Silicon Mac
            opus_path = "/opt/homebrew/lib/libopus.0.dylib"
            
            try:
                discord.opus.load_opus(opus_path)
                logger.info(f"SUCCESS: Loaded Opus from {opus_path}")
            except Exception as e:
                logger.warning(f"Failed to load from primary path: {e}")
                
                # Fall back to other paths if the specific one fails
                opus_paths = [
                    'opus', 'libopus.0.dylib',
                    '/opt/homebrew/lib/libopus.dylib',
                    '/opt/homebrew/Cellar/opus/1.5.2/lib/libopus.0.dylib',
                    'libopus.so.0', 'libopus.so',
                    'opus.dll'
                ]
                
                for path in opus_paths:
                    try:
                        discord.opus.load_opus(path)
                        logger.info(f"SUCCESS: Loaded Opus from {path}")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to load Opus from {path}: {e}")
                        continue
            
            if not discord.opus.is_loaded():
                logger.warning("WARNING: Could not load Opus library. Voice functions won't work.")
        except Exception as e:
            logger.error(f"Error in Opus loading process: {e}") 