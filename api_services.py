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

logger = logging.getLogger(__name__)

def transcribe_audio(audio_data):
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
        
        # ElevenLabs requires multipart/form-data with 'file' field and 'model_id'
        with open(temp_file_path, "rb") as audio_file:
            files = {"file": audio_file}
            data = {"model_id": "scribe_v1"}
            
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
                logger.error(f"Could not parse response as JSON")
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

def get_elevenlabs_voices():
    """Fetch all available voices from ElevenLabs API"""
    api_key = ELEVENLABS_API_KEY
    if not api_key:
        logger.error("ELEVENLABS_API_KEY is missing")
        return []
    
    headers = {
        "xi-api-key": api_key
    }
    
    try:
        response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        response.raise_for_status()
        voices = response.json().get("voices", [])
        return voices
    except Exception as e:
        logger.error(f"Error fetching ElevenLabs voices: {e}")
        return []

def select_voice_for_language(target_lang, voices=None):
    """Select appropriate voice for target language"""
    if voices is None:
        voices = get_elevenlabs_voices()
    
    logger.info(f"Selecting voice for language {target_lang}. Found {len(voices)} voices.")
    
    # Define preferred voices for common languages
    language_voice_map = {
        "Spanish": ["Antonio", "Mia", "Pedro"],
        "French": ["Nicole", "Rémi", "Alain"],
        "German": ["Hans", "Greta", "Stefan"],
        "Italian": ["Valentina", "Matteo", "Gianni"],
        "Portuguese": ["Thiago", "Luiza"],
        "Japanese": ["Hiroto", "Yuka"],
        "Chinese": ["Li", "Wang"],
        "Russian": ["Alexei", "Natasha"],
        # Add more language-voice mappings as needed
    }
    
    # Default to English voice if no match
    default_voices = ["Adam", "Bella", "Josh"]
    
    # Get preferred voices for target language
    preferred_voices = language_voice_map.get(target_lang, default_voices)
    logger.info(f"Preferred voices for {target_lang}: {preferred_voices}")
    
    # Find first available preferred voice
    for preferred_name in preferred_voices:
        for voice in voices:
            voice_name = voice.get("name", "")
            if preferred_name.lower() in voice_name.lower():
                voice_id = voice.get("voice_id")
                logger.info(f"Found matching voice: {voice_name} (ID: {voice_id})")
                return voice_id
    
    # If no preferred voice found, return first available voice
    if voices:
        first_voice_id = voices[0].get("voice_id")
        first_voice_name = voices[0].get("name", "")
        logger.info(f"No preferred voice found, using first available: {first_voice_name} (ID: {first_voice_id})")
        return first_voice_id
    
    logger.warning("No voices available, falling back to default voice ID")
    return ELEVENLABS_VOICE_ID  # Return the default voice ID

def generate_speech(text, voice_id=None):
    """Generate speech from text using ElevenLabs API"""
    try:
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.5
            }
        }
        
        # Use provided voice_id, fall back to default ELEVENLABS_VOICE_ID
        voice_id_to_use = voice_id if voice_id else ELEVENLABS_VOICE_ID
        
        if not voice_id_to_use:
            logger.error("No voice ID provided and no default voice ID configured")
            return None
            
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
            
            return temp_file_path
        else:
            logger.error(f"TTS error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        return None 