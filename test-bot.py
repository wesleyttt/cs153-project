import discord
from discord.ext import commands
import asyncio
import queue
import threading
import io
import requests
import tempfile
import os
from pydub import AudioSegment
from dotenv import load_dotenv
from discord.sinks import Sink
import sys
import logging
import time

# Load environment variables
load_dotenv()

# Add function to load from secrets.txt
def load_secrets_from_file(filename="secrets.txt"):
    secrets = {}
    try:
        with open(filename, 'r') as file:
            for line in file:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    secrets[key] = value
        print(f"Loaded secrets from {filename}")
        return secrets
    except Exception as e:
        print(f"Error loading secrets from {filename}: {e}")
        return {}

# Load secrets from file
secrets = load_secrets_from_file()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Discord bot with voice intents
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Load Opus - specifically using your Mac's path
if not discord.opus.is_loaded():
    try:
        # For Apple Silicon Mac - using the path you found
        opus_path = "/opt/homebrew/lib/libopus.0.dylib"
        
        try:
            discord.opus.load_opus(opus_path)
            print(f"SUCCESS: Loaded Opus from {opus_path}")
        except Exception as e:
            print(f"Failed to load from primary path: {e}")
            
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
                    print(f"SUCCESS: Loaded Opus from {path}")
                    break
                except Exception as e:
                    print(f"Failed to load Opus from {path}: {e}")
                    continue
        
        if not discord.opus.is_loaded():
            print("WARNING: Could not load Opus library. Voice functions won't work.")
    except Exception as e:
        print(f"Error in Opus loading process: {e}")

# API Keys - prioritize env vars but fall back to secrets.txt
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY") or secrets.get("ELEVENLABS_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY") or secrets.get("MISTRAL_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or secrets.get("DISCORD_TOKEN")

# Verify API keys are loaded
if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found in environment or secrets.txt")
    sys.exit(1)
    
if not ELEVENLABS_API_KEY:
    print("WARNING: ELEVENLABS_API_KEY not found - speech features will not work")

if not MISTRAL_API_KEY:
    print("WARNING: MISTRAL_API_KEY not found - translation features will not work")

# API URLs
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Default ElevenLabs voice ID
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# Custom audio sink for Discord voice
class TranslationSink(Sink):
    def __init__(self, user_queues):
        self.user_queues = user_queues
        self.processing_threads = {}  # Track active processing threads
        super().__init__()

    def write(self, data, user_id):
        print(f"Audio data received from user {user_id}, size: {len(data)} bytes")
        
        # Check if we need to create a new queue and processing thread
        if user_id not in self.user_queues or user_id not in self.processing_threads or not self.processing_threads[user_id].is_alive():
            print(f"Creating new queue and thread for user {user_id}")
            self.user_queues[user_id] = queue.Queue()
            
            # Get target language from bot settings
            target_lang = getattr(bot, 'target_language', 'Spanish')
            
            # Start processing thread
            text_channel = getattr(self, 'text_channel', None)
            voice_client = getattr(self, 'voice_client', None)
            if text_channel and voice_client:
                thread = threading.Thread(
                    target=process_user_audio,
                    args=(user_id, self.user_queues[user_id], text_channel, voice_client, target_lang)
                )
                thread.daemon = True  # Make thread exit when main program exits
                thread.start()
                self.processing_threads[user_id] = thread
        
        # Add data to the queue
        self.user_queues[user_id].put(data)

    def cleanup(self):
        print("TranslationSink cleanup called")
        for user_id in list(self.user_queues.keys()):
            self.user_queues[user_id].put(None)  # Signal threads to end

# Speech-to-text using ElevenLabs
def transcribe_audio(audio_data):
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
        print(f"Saved audio to temporary file: {temp_file_path}")
    
    try:
        # Call ElevenLabs API with the required fields
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        print("Sending request to ElevenLabs STT API...")
        
        # ElevenLabs requires multipart/form-data with 'file' field and 'model_id'
        with open(temp_file_path, "rb") as audio_file:
            files = {"file": audio_file}  # Changed from "audio" to "file"
            data = {"model_id": "scribe_v1"}  # Added required model_id
            
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
            print(f"Transcription successful: '{result}'")
            return result
        else:
            print(f"Transcription error: {response.status_code} - {response.text}")
            return ""
            
    except Exception as e:
        print(f"Error in transcription: {e}")
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return ""

# Translation using Mistral
def translate_text(text, source_lang="English", target_lang="Spanish"):
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
            print(f"Translation error: {response.status_code} - {response.text}")
            return text
    except Exception as e:
        print(f"Error in translation: {e}")
        return text

# Text-to-speech using ElevenLabs
def generate_speech(text, voice_id=ELEVENLABS_VOICE_ID):
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
            print(f"TTS error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        return None

# Process user audio in a separate thread
def process_user_audio(user_id, audio_queue, text_channel, voice_client, target_lang="Spanish"):
    print(f"Started processing audio for user {user_id}")
    accumulated_audio = bytearray()
    silence_threshold = 0.5  # seconds of silence to consider end of speech
    last_audio_time = None
    
    while True:
        try:
            # Wait for audio data with timeout
            chunk = audio_queue.get(timeout=silence_threshold)
            if chunk is None:  # End signal
                print(f"End signal received for user {user_id}")
                break
                
            accumulated_audio.extend(chunk)
            print(f"Received audio chunk from user {user_id}, total size: {len(accumulated_audio)} bytes")
            last_audio_time = time.time()
            
        except queue.Empty:
            # Process accumulated audio when silence is detected
            if accumulated_audio and last_audio_time and (time.time() - last_audio_time) >= silence_threshold:
                print(f"Processing accumulated audio for user {user_id}, size: {len(accumulated_audio)} bytes")
                
                try:
                    # Step 1: Transcribe the audio
                    print("Calling transcribe_audio...")
                    transcription = transcribe_audio(accumulated_audio)
                    print(f"Transcription result: '{transcription}'")
                    
                    if transcription:
                        # Step 2: Translate the text
                        print(f"Translating text to {target_lang}...")
                        translation = translate_text(
                            transcription, 
                            source_lang="English", 
                            target_lang=target_lang
                        )
                        print(f"Translation result: '{translation}'")
                        
                        # Step 3: Send text to Discord
                        asyncio.run_coroutine_threadsafe(
                            text_channel.send(f'**User {user_id}**: {transcription}\n**Translated**: {translation}'),
                            bot.loop
                        )
                        
                        # Step 4: Generate and play speech
                        print("Generating speech...")
                        audio_file_path = generate_speech(translation)
                        if audio_file_path and voice_client and voice_client.is_connected():
                            print(f"Playing audio from {audio_file_path}")
                            asyncio.run_coroutine_threadsafe(
                                play_audio(voice_client, audio_file_path),
                                bot.loop
                            )
                        else:
                            print(f"Failed to play audio: file_path={audio_file_path}, voice_client_connected={voice_client and voice_client.is_connected()}")
                    else:
                        print("No transcription result, skipping translation")
                except Exception as e:
                    print(f"Error processing audio: {e}")
                
                # Reset for next utterance
                accumulated_audio = bytearray()

# Play audio in Discord voice channel
async def play_audio(voice_client, file_path):
    if voice_client and voice_client.is_connected():
        # Pause recording while playing
        was_recording = voice_client.recording
        if was_recording:
            voice_client.stop_recording()
        
        # Play the audio
        voice_client.play(discord.FFmpegPCMAudio(file_path))
        
        # Wait for playback to complete
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        
        # Clean up
        os.unlink(file_path)
        
        # Resume recording with proper callback format
        if was_recording:
            # Recreate the sink with existing settings
            if hasattr(voice_client, 'last_sink'):
                sink = voice_client.last_sink
                
                # Make sure we preserve the original text channel reference
                original_text_channel = getattr(voice_client, 'original_text_channel', None)
                if original_text_channel:
                    sink.text_channel = original_text_channel
            else:
                # Create new sink if we don't have reference to the old one
                user_queues = getattr(voice_client, 'user_queues', {})
                sink = TranslationSink(user_queues)
                
                # Use the stored original channel reference
                original_text_channel = getattr(voice_client, 'original_text_channel', None)
                if original_text_channel:
                    sink.text_channel = original_text_channel
                else:
                    # Fallback to finding any text channel only if necessary
                    text_channel = None
                    for guild in bot.guilds:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                text_channel = channel
                                break
                        if text_channel:
                            break
                    sink.text_channel = text_channel
            
            # Always set the voice_client reference
            sink.voice_client = voice_client
            
            # Store reference to sink for future use
            voice_client.last_sink = sink
            
            # Use a lambda with no parameters for the callback
            voice_client.start_recording(sink, lambda: print('Resumed recording'))
            print("Recording resumed after audio playback")

# Monitor speaking events in voice channel
async def monitor_speaking(voice_client, user_queues, text_channel):
    print("Monitor speaking started")
    while True:
        user, speaking = await voice_client.receiver.speaking.get()
        print(f"Speaking event: User {user.id} speaking: {speaking}")
        
        if speaking and user not in user_queues:
            # User started speaking
            print(f"User {user.id} started speaking, creating queue")
            audio_queue = queue.Queue()
            user_queues[user] = audio_queue
            
            # Get target language from bot settings
            target_lang = getattr(bot, 'target_language', 'Spanish')
            
            # Start processing thread
            threading.Thread(
                target=process_user_audio,
                args=(user.id, audio_queue, text_channel, voice_client, target_lang)
            ).start()
        elif not speaking and user in user_queues:
            # User stopped speaking
            print(f"User {user.id} stopped speaking")
            user_queues[user].put(None)  # Signal thread to end
            del user_queues[user]

# Bot command to join voice channel
@bot.command()
async def join(ctx):
    # Check if already in a voice channel
    if ctx.voice_client:
        await ctx.send('I am already in a voice channel. Use !leave first.')
        return
        
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        try:
            print(f"Attempting to join voice channel: {channel}")
            voice_client = await channel.connect()
            
            # Store the original text channel where the command was issued
            voice_client.original_text_channel = ctx.channel
            print(f"Original text channel set to: {ctx.channel.name}")
            
            # Start recording
            user_queues = {}
            sink = TranslationSink(user_queues)
            
            # Store references to important objects in the sink
            sink.text_channel = ctx.channel
            sink.voice_client = voice_client
            
            # Store sink reference in voice_client for reuse later
            voice_client.last_sink = sink
            
            # Start recording with the correct callback format
            voice_client.start_recording(sink, lambda: print('Recording ended'))
            print("Recording started")
            
            # Store user_queues in voice_client for reference elsewhere
            voice_client.user_queues = user_queues
            
            await ctx.send(f'Joined {channel} and started translating. Speak clearly to test.')
        except Exception as e:
            print(f"Error joining channel: {e}")
            await ctx.send(f'Error joining voice channel: {str(e)}')
    else:
        await ctx.send('You need to be in a voice channel first.')

# Bot command to leave voice channel
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop_recording()
        await ctx.voice_client.disconnect()
        await ctx.send('Left the voice channel.')
    else:
        await ctx.send('I am not in a voice channel.')

# Bot command to set target language
@bot.command()
async def setlang(ctx, language):
    """Set the target translation language"""
    bot.target_language = language
    await ctx.send(f"Target language set to {language}")

# Bot command to list available languages
@bot.command()
async def languages(ctx):
    """List common available languages"""
    common_languages = [
        "Spanish", "French", "German", "Italian", "Portuguese", 
        "Russian", "Japanese", "Chinese", "Korean", "Arabic",
        "Hindi", "Dutch", "Swedish", "Greek", "Turkish"
    ]
    await ctx.send("Common available languages:\n" + "\n".join(common_languages))
    await ctx.send("You can try other languages as well - Mistral supports many languages.")

# Bot command to show information
@bot.command()
async def info(ctx):
    target_lang = getattr(bot, 'target_language', 'Spanish')
    
    info_message = (
        f"**Discord Voice Translator**\n"
        f"- Target Language: {target_lang}\n"
        f"- Speech Recognition: ElevenLabs\n"
        f"- Translation: Mistral AI\n"
        f"- Text-to-Speech: ElevenLabs\n\n"
        f"**Commands**\n"
        f"- `!join` - Join your voice channel and start translating\n"
        f"- `!leave` - Leave the voice channel\n"
        f"- `!setlang [language]` - Set target language\n"
        f"- `!languages` - List available languages\n"
        f"- `!info` - Show this information"
    )
    
    await ctx.send(info_message)

# Bot ready event
@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    print(f'Bot ID: {bot.user.id}')
    print(f'Opus loaded: {discord.opus.is_loaded()}')
    print(f'Use !join in a Discord server to start translating')

# Add a simple debug command
@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

# Add error handling for commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Command not found. Try `!info` for available commands.")
    else:
        print(f"Command error: {error}")
        await ctx.send(f"Error: {error}")

# Run the bot
bot.run(DISCORD_TOKEN)