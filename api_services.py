import requests
import tempfile
import os
import io
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
    # Convert audio data to proper format
    audio = AudioSegment.from_raw(
        io.BytesIO(audio_data),
        sample_width=2,
        frame_rate=48000,
        channels=2
    )
    
    # Convert to mono and set appropriate sample rate
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        audio.export(temp_file.name, format="mp3")
        temp_file_path = temp_file.name
        logger.info(f"Saved audio to temporary file: {temp_file_path}")
    
    try:
        # Call ElevenLabs API with the required fields
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        logger.info("Sending request to ElevenLabs STT API...")
        
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
        os.unlink(temp_file_path)
        
        if response.status_code == 200:
            result = response.json().get("text", "")
            logger.info(f"Transcription successful: '{result}'")
            return result
        else:
            logger.error(f"Transcription error: {response.status_code} - {response.text}")
            return ""
            
    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        if os.path.exists(temp_file_path):
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

def generate_speech(text, voice_id=ELEVENLABS_VOICE_ID):
    """Generate speech from text using ElevenLabs API"""
    try:
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        response = requests.post(
            f"{ELEVENLABS_TTS_URL}/{voice_id}",
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