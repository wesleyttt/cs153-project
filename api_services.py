import requests
import tempfile
import os
import io
import json
from pydub import AudioSegment
import logging
from config import (
    ELEVENLABS_API_KEY, MISTRAL_API_KEY, 
    ELEVENLABS_TTS_URL, ELEVENLABS_STT_URL, 
    MISTRAL_API_URL, ELEVENLABS_VOICE_ID
)
import pathlib

logger = logging.getLogger(__name__)

# Ensure voices.json exists with valid JSON
def ensure_voices_json_exists():
    """Create voices.json if it doesn't exist or is invalid"""
    if not pathlib.Path("voices.json").exists() or pathlib.Path("voices.json").stat().st_size == 0:
        try:
            with open("voices.json", "w") as f:
                f.write('[]')  # Empty valid JSON array
            logger.info("Created empty voices.json file")
        except Exception as e:
            logger.error(f"Failed to create voices.json: {e}")

# Call this function
ensure_voices_json_exists()

def transcribe_audio(audio_data, source_lang="English"):
    """Convert audio to text using ElevenLabs API"""
    # Directly convert to the required format without intermediate steps
    audio = AudioSegment.from_raw(
        io.BytesIO(audio_data),
        sample_width=2,
        frame_rate=48000,
        channels=2
    ).set_channels(1).set_frame_rate(16000)
    
    # Use in-memory file instead of disk when possible
    temp_buffer = io.BytesIO()
    audio.export(temp_buffer, format="mp3")
    temp_buffer.seek(0)
    
    # Use the buffer directly in the request
    files = {"file": ("audio.mp3", temp_buffer, "audio/mp3")}
    
    try:
        # Call ElevenLabs API with the required fields
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        logger.info(f"Sending request to ElevenLabs STT API for {source_lang} speech...")
        
        # ElevenLabs requires multipart/form-data with 'file' field and 'model_id'
        response = requests.post(
            ELEVENLABS_STT_URL,
            headers=headers,
            files=files,
            data={
                "model_id": "scribe_v1",
                # Add language hint if not English
                "language": source_lang.lower() if source_lang.lower() != "english" else None
            }
        )
        
        if response.status_code == 200:
            result = response.json().get("text", "")
            logger.info(f"Transcription successful: '{result}'")
            return result
        else:
            logger.error(f"Transcription error: {response.status_code} - {response.text}")
            return ""
            
    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        return ""

def translate_text(text, source_lang="English", target_lang="Spanish"):
    """Translate text using Mistral AI"""
    if not text.strip():
        return ""
        
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "open-mistral-nemo",
        "messages": [
            {
                "role": "system", 
                "content": f"You are a translator. Translate the following text from {source_lang} to {target_lang}. Only respond with the translated text, nothing else."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"Translation error: {response.status_code} - {response.text}")
            return text
    except Exception as e:
        logger.error(f"Error in translation: {e}")
        return text

def select_voice_for_user(user_id, target_lang=None):
    """
    Select a voice for a specific user using voices.json file
    
    Args:
        user_id: The ID of the user
        target_lang: Parameter kept for backward compatibility but no longer used
    
    Returns:
        The voice ID to use
    """
    try:
        # Try to load voices from json file
        try:
            with open("voices.json", "r") as file:
                content = file.read().strip()
                # Check if file is empty
                if not content:
                    logger.warning("voices.json file is empty, using default voice")
                    return ELEVENLABS_VOICE_ID
                voices = json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load voices.json: {e}. Using default voice.")
            return ELEVENLABS_VOICE_ID
        
        if not voices or not isinstance(voices, list) or len(voices) == 0:
            logger.warning("No usable voices found in voices.json")
            return ELEVENLABS_VOICE_ID
        
        # Use hash function to consistently map user to a voice
        voice_index = hash(str(user_id)) % len(voices)
        selected_voice = voices[voice_index]
        voice_id = selected_voice.get("voice_id")
        voice_name = selected_voice.get("name", "Unknown")
        
        logger.info(f"Selected voice for user {user_id}: {voice_name} (ID: {voice_id})")
        return voice_id
            
    except Exception as e:
        logger.error(f"Error selecting voice for user: {e}")
        return ELEVENLABS_VOICE_ID  # Fall back to default voice ID

def generate_speech(text, voice_id=None, user_id=None, target_lang=None):
    """Generate speech from text using ElevenLabs API"""
    try:
        # If no specific voice_id is provided, select based on user and/or language
        if not voice_id:
            if user_id:
                voice_id = select_voice_for_user(user_id, target_lang)
            elif target_lang:
                # For backward compatibility - if only language is provided
                voice_id = select_voice_for_user("default_user", target_lang)
        
        # Ensure we have a valid voice_id
        voice_id_to_use = voice_id if voice_id else ELEVENLABS_VOICE_ID
        
        if not voice_id_to_use:
            logger.error("No voice ID provided and no default voice ID configured")
            return None
            
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"  # Explicitly specify the expected response format
        }
        
        # Enhanced payload with streaming optimization
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            },
            "output_format": "mp3_44100_128",  # Optimized format
            "optimize_streaming_latency": 4    # Range 1-4, higher = lower latency
        }
        
        logger.info(f"Generating speech with voice ID: {voice_id_to_use}")
        
        # Use stream=True for request
        response = requests.post(
            f"{ELEVENLABS_TTS_URL}/{voice_id_to_use}",
            headers=headers,
            json=payload,
            stream=True,
            timeout=30  # Add explicit timeout
        )
        
        if response.status_code == 200:
            # Save to temporary file with better error handling
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    # Stream the content to file to avoid loading everything into memory
                    for chunk in response.iter_content(chunk_size=4096):
                        if chunk:
                            temp_file.write(chunk)
                    temp_file_path = temp_file.name
                    
                logger.info(f"Successfully saved audio to {temp_file_path}")
                return temp_file_path
            except Exception as file_error:
                logger.error(f"Error saving audio file: {file_error}")
                return None
        else:
            logger.error(f"TTS error: {response.status_code} - {response.text}")
            # Try to get more detailed error information
            error_details = response.text
            try:
                error_json = response.json()
                error_details = f"{error_json.get('detail', '')}"
            except:
                pass
            logger.error(f"Error details: {error_details}")
            return None
            
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        return None

def get_audio_file_bytes(file_path):
    """Read an audio file and return its bytes"""
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading audio file: {e}")
        return None

def get_language_code(language_name):
    """Convert language name to language code used by the API"""
    language_map = {
        "English": "en",
        "Spanish": "es",
        "French": "fr",
        "German": "de",
        "Italian": "it",
        "Portuguese": "pt",
        "Japanese": "ja",
        "Chinese": "zh",
        "Russian": "ru",
        "Korean": "ko",
        "Dutch": "nl",
        "Hindi": "hi",
        "Arabic": "ar"
    }
    
    return language_map.get(language_name, "en")  # Default to English if not found 