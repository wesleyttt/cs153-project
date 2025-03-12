import requests
import tempfile
import os
import io
import re
from pydub import AudioSegment
import logging
from config import (
    ELEVENLABS_API_KEY, MISTRAL_API_KEY, 
    ELEVENLABS_TTS_URL, ELEVENLABS_STT_URL, 
    MISTRAL_API_URL, ELEVENLABS_VOICE_ID
)
import json
import random

logger = logging.getLogger(__name__)

# Language code mapping
LANGUAGE_CODES = {
    "english": "en",
    "spanish": "es", 
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "polish": "pl",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "hindi": "hi",
    "arabic": "ar",
    "russian": "ru",
    "dutch": "nl",
    "turkish": "tr",
    "indonesian": "id",
    "czech": "cs",
    "danish": "da",
    "finnish": "fi",
    "greek": "el",
    "hebrew": "he",
    "hungarian": "hu",
    "norwegian": "no",
    "romanian": "ro",
    "swedish": "sv",
    "thai": "th",
    "vietnamese": "vi",
    "ukrainian": "uk"
}

def transcribe_audio(audio_data, user_id=None):
    """Convert audio to text using ElevenLabs API"""
    if not audio_data or len(audio_data) < 1000:
        logger.warning(f"Audio data too small to process: {len(audio_data) if audio_data else 0} bytes")
        return ""
        
    logger.info(f"Processing audio data of size: {len(audio_data)} bytes")
    
    # Convert audio data to proper format
    try:
        audio = AudioSegment.from_raw(
            io.BytesIO(audio_data),
            sample_width=2,
            frame_rate=48000,
            channels=2
        )
        
        # Convert to mono and set appropriate sample rate
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
        
        logger.info(f"Converted audio: {len(audio.raw_data)} bytes, {audio.frame_rate}Hz, {audio.channels} channel(s)")
    except Exception as e:
        logger.error(f"Error converting audio format: {e}")
        return ""
    
    # Save to temporary file
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            audio.export(temp_file.name, format="mp3")
            temp_file_path = temp_file.name
            logger.info(f"Saved audio to temporary file: {temp_file_path}, size: {os.path.getsize(temp_file_path)} bytes")
    except Exception as e:
        logger.error(f"Error saving audio to temp file: {e}")
        return ""
    
    try:
        # Call ElevenLabs API with the required fields
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        logger.info("Sending request to ElevenLabs STT API...")
        
        # Verify the API key is not empty
        if not ELEVENLABS_API_KEY:
            logger.error("ELEVENLABS_API_KEY is missing or empty")
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            return ""
        
        # Get user input language and convert to language code if user_id is provided
        language_code = None
        if user_id:
            input_language = get_user_input_language(user_id)
            language_code = get_language_code(input_language)
            logger.info(f"Using language code '{language_code}' for transcription in '{input_language}'")
        
        # ElevenLabs requires multipart/form-data with 'file' field and 'model_id'
        with open(temp_file_path, "rb") as audio_file:
            files = {"file": audio_file}
            data = {"model_id": "scribe_v1"}
            
            # Add language code if available
            if language_code:
                data["language"] = language_code
            
            response = requests.post(
                ELEVENLABS_STT_URL,
                headers=headers,
                files=files,
                data=data
            )
        
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.info(f"Deleted temporary file: {temp_file_path}")
        
        if response.status_code == 200:
            result = response.json().get("text", "")
            logger.info(f"Transcription successful: '{result}'")
            
            # Filter out text within parentheses (sound effects, background noises)
            filtered_result = re.sub(r'\([^)]*\)', '', result).strip()
            if filtered_result != result:
                logger.info(f"Filtered transcription: '{filtered_result}'")
                # Only return filtered result if it contains actual content
                if filtered_result:
                    return filtered_result
                # If filtering removed all content, return empty string
                return ""
            return result
        else:
            logger.error(f"Transcription error: {response.status_code} - {response.text}")
            # Add full response dump for debugging
            try:
                logger.error(f"Full response: {response.json()}")
            except:
                logger.error("Could not parse response as JSON")
            return ""
            
    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
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
        "model": "mistral-small-latest",
        "messages": [
            {
                "role": "system",
                "content": f"""You are a translator. Translate the following text from {source_lang} to {target_lang}. Only respond with the translated text, nothing else. If the input is a question, do not respond to the question, only respond with the translated question.

                Example: source_lang = English, target_lang = Spanish
                Input: What is the capital of France?
                Output: ¿Cuál es la capital de Francia?

                Example: source_lang = Chinese, target_lang = English  
                Input: 你現在在講什麼語言？
                Output: What language are you speaking now?

                Example: source_lang = Spanish, target_lang = French
                Input: El clima es agradable hoy.
                Output: Il fait beau aujourd'hui.

                ----
                Current translation:
                From {source_lang} to {target_lang}
                Input: """
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

def get_elevenlabs_voices():
    """Fetch all available voices from voices.json"""
    try:
        with open("voices.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("Error loading voices.json")
        return []

def get_language_code(language, default="en"):
    """Get the ISO language code for a language name"""
    if not language:
        return default
    return LANGUAGE_CODES.get(language.lower(), default)

def generate_speech(text, voice_id=None, user_id=None):
    """Generate speech from text using ElevenLabs API"""
    if not text or not text.strip():
        logger.warning("Empty text provided to speech generation")
        return None
        
    try:
        # Verify API key first
        if not ELEVENLABS_API_KEY:
            logger.error("ELEVENLABS_API_KEY is missing or empty")
            return None
            
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Get user output language and convert to language code
        output_language = get_user_output_language(user_id)
        language_code = get_language_code(output_language)
        logger.info(f"Using language code '{language_code}' for language '{output_language}'")
        
        # Log text being converted (truncate if too long)
        display_text = text if len(text) < 100 else f"{text[:97]}..."
        logger.info(f"Converting text to speech: '{display_text}'")
        
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.5
            },
            "language_code": language_code
        }
        
        # First check for user-specific voice if user_id is provided
        voice_id_to_use = None
        if user_id:
            voice_id_to_use = get_user_voice(user_id)
            logger.info(f"Using user-specific voice ID for user {user_id}: {voice_id_to_use}")
        
        # Fall back to provided voice_id if user doesn't have an assigned voice
        if not voice_id_to_use:
            voice_id_to_use = voice_id if voice_id else ELEVENLABS_VOICE_ID
            logger.info(f"Falling back to voice ID: {voice_id_to_use}")
        
        if not voice_id_to_use:
            logger.error("No voice ID determined and no default voice ID configured")
            return None
            
        logger.info(f"Sending TTS request to ElevenLabs API with voice ID: {voice_id_to_use}")
        response = requests.post(
            f"{ELEVENLABS_TTS_URL}/{voice_id_to_use}",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
                
            # Log successful audio generation with details
            file_size = os.path.getsize(temp_file_path)
            logger.info(f"Successfully generated audio file: {temp_file_path} ({file_size} bytes)")
            
            return temp_file_path
        else:
            logger.error(f"TTS error: {response.status_code} - {response.text}")
            try:
                logger.error(f"Full error response: {response.json()}")
            except:
                logger.error("Could not parse error response as JSON")
            return None
            
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        return None

def load_voice_assignments():
    """Load user voice assignments from user_voice_assignments.json"""
    try:
        with open("user_voice_assignments.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("No existing voice assignments found or invalid JSON. Creating new assignments.")
        return {}

def save_voice_assignments(assignments):
    """Save user voice assignments to user_voice_assignments.json"""
    with open("user_voice_assignments.json", "w") as f:
        json.dump(assignments, f, indent=2)
    logger.info(f"Saved voice assignments for {len(assignments)} users")

def get_user_voice(user_id):
    """Get a user's assigned voice ID, or assign a new one if none exists"""
    assignments = load_voice_assignments()
    
    # If user already has an assigned voice, return it
    if str(user_id) in assignments:
        voice_id = assignments[str(user_id)]
        logger.info(f"Found existing voice assignment for user {user_id}: {voice_id}")
        return voice_id
    
    # Otherwise, assign a new voice randomly
    voices = get_elevenlabs_voices()
    
    if not voices:
        logger.warning("No voices available to assign to user")
        return ELEVENLABS_VOICE_ID
    
    # Pick a random voice
    random_voice = random.choice(voices)
    voice_id = random_voice.get("voice_id")
    
    # Save the assignment
    assignments[str(user_id)] = voice_id
    save_voice_assignments(assignments)
    logger.info(f"Assigned new voice to user {user_id}: {voice_id}")
    return voice_id

def assign_voice_to_user(user_id, voice_id):
    """Manually assign a specific voice to a user"""
    assignments = load_voice_assignments()
    assignments[str(user_id)] = voice_id
    save_voice_assignments(assignments)
    logger.info(f"Manually assigned voice {voice_id} to user {user_id}")
    return True

def load_user_languages():
    """Load user language preferences from user_languages.json"""
    try:
        with open("user_languages.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("No existing language preferences found or invalid JSON. Creating new preferences file.")
        return {}

def save_user_languages(language_prefs):
    """Save user language preferences to user_languages.json"""
    with open("user_languages.json", "w") as f:
        json.dump(language_prefs, f, indent=2)
    logger.info(f"Saved language preferences for {len(language_prefs)} users")

def get_user_input_language(user_id, default="English"):
    """Get a user's input language preference, or return default if none exists"""
    preferences = load_user_languages()
    user_id_str = str(user_id)
    
    if user_id_str in preferences and "input" in preferences[user_id_str]:
        language = preferences[user_id_str]["input"]
        logger.info(f"Found existing input language for user {user_id}: {language}")
        return language
        
    # If no preference exists, return default
    logger.info(f"No input language preference for user {user_id}, using default: {default}")
    return default
    
def get_user_output_language(user_id, default="Spanish"):
    """Get a user's output language preference, or return default if none exists"""
    preferences = load_user_languages()
    user_id_str = str(user_id)
    
    if user_id_str in preferences and "output" in preferences[user_id_str]:
        language = preferences[user_id_str]["output"]
        logger.info(f"Found existing output language for user {user_id}: {language}")
        return language
        
    # If no preference exists, return default
    logger.info(f"No output language preference for user {user_id}, using default: {default}")
    return default

def set_user_input_language(user_id, language):
    """Set a user's input language preference"""
    preferences = load_user_languages()
    user_id_str = str(user_id)
    
    if user_id_str not in preferences:
        preferences[user_id_str] = {}
    
    preferences[user_id_str]["input"] = language
    save_user_languages(preferences)
    logger.info(f"Set input language for user {user_id} to {language}")
    return True

def set_user_output_language(user_id, language):
    """Set a user's output language preference"""
    preferences = load_user_languages()
    user_id_str = str(user_id)
    
    if user_id_str not in preferences:
        preferences[user_id_str] = {}
    
    preferences[user_id_str]["output"] = language
    save_user_languages(preferences)
    logger.info(f"Set output language for user {user_id} to {language}")
    return True 