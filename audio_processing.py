import asyncio
import queue
import threading
import time
import os
import logging
import discord
from discord.sinks import Sink
from api_services import transcribe_audio, translate_text, generate_speech

logger = logging.getLogger(__name__)

class TranslationSink(Sink):
    def __init__(self, user_queues):
        self.user_queues = user_queues
        self.processing_threads = {}  # Track active processing threads
        super().__init__()

    def write(self, data, user_id):
        logger.info(f"Audio data received from user {user_id}, size: {len(data)} bytes")
        
        # Check if we need to create a new queue and processing thread
        if user_id not in self.user_queues or user_id not in self.processing_threads or not self.processing_threads[user_id].is_alive():
            logger.info(f"Creating new queue and thread for user {user_id}")
            self.user_queues[user_id] = queue.Queue()
            
            # Get target language from bot settings
            bot = getattr(self, 'bot', None)
            target_lang = getattr(bot, 'target_language', 'Spanish') if bot else 'Spanish'
            
            # Start processing thread
            text_channel = getattr(self, 'text_channel', None)
            voice_client = getattr(self, 'voice_client', None)
            if text_channel and voice_client:
                thread = threading.Thread(
                    target=process_user_audio,
                    args=(user_id, self.user_queues[user_id], text_channel, voice_client, target_lang, bot)
                )
                thread.daemon = True  # Make thread exit when main program exits
                thread.start()
                self.processing_threads[user_id] = thread
        
        # Add data to the queue
        self.user_queues[user_id].put(data)

    def cleanup(self):
        logger.info("TranslationSink cleanup called")
        for user_id in list(self.user_queues.keys()):
            self.user_queues[user_id].put(None)  # Signal threads to end

def process_user_audio(user_id, audio_queue, text_channel, voice_client, target_lang="Spanish", bot=None):
    """Process audio from a user in a separate thread"""
    logger.info(f"Started processing audio for user {user_id}")
    accumulated_audio = bytearray()
    silence_threshold = 0.5  # seconds of silence to consider end of speech
    last_audio_time = None
    
    while True:
        try:
            # Wait for audio data with timeout
            chunk = audio_queue.get(timeout=silence_threshold)
            if chunk is None:  # End signal
                logger.info(f"End signal received for user {user_id}")
                break
                
            accumulated_audio.extend(chunk)
            logger.info(f"Received audio chunk from user {user_id}, total size: {len(accumulated_audio)} bytes")
            last_audio_time = time.time()
            
        except queue.Empty:
            # Process accumulated audio when silence is detected
            if accumulated_audio and last_audio_time and (time.time() - last_audio_time) >= silence_threshold:
                logger.info(f"Processing accumulated audio for user {user_id}, size: {len(accumulated_audio)} bytes")
                
                try:
                    # Step 1: Transcribe the audio
                    logger.info("Calling transcribe_audio...")
                    transcription = transcribe_audio(accumulated_audio)
                    logger.info(f"Transcription result: '{transcription}'")
                    
                    if transcription:
                        # Step 2: Translate the text
                        logger.info(f"Translating text to {target_lang}...")
                        translation = translate_text(
                            transcription, 
                            source_lang="English", 
                            target_lang=target_lang
                        )
                        logger.info(f"Translation result: '{translation}'")
                        
                        # Step 3: Send text to Discord
                        asyncio.run_coroutine_threadsafe(
                            text_channel.send(f'**User {user_id}**: {transcription}\n**Translated**: {translation}'),
                            bot.loop if bot else asyncio.get_event_loop()
                        )
                        
                        # Step 4: Generate and play speech
                        logger.info("Generating speech...")
                        audio_file_path = generate_speech(translation)
                        if audio_file_path and voice_client and voice_client.is_connected():
                            logger.info(f"Playing audio from {audio_file_path}")
                            asyncio.run_coroutine_threadsafe(
                                play_audio(voice_client, audio_file_path),
                                bot.loop if bot else asyncio.get_event_loop()
                            )
                        else:
                            logger.warning(f"Failed to play audio: file_path={audio_file_path}, voice_client_connected={voice_client and voice_client.is_connected()}")
                    else:
                        logger.warning("No transcription result, skipping translation")
                except Exception as e:
                    logger.error(f"Error processing audio: {e}")
                
                # Reset for next utterance
                accumulated_audio = bytearray()

async def play_audio(voice_client, file_path):
    """Play audio in Discord voice channel"""
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
                    for guild in voice_client.bot.guilds:
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
            voice_client.start_recording(sink, lambda: logger.info('Resumed recording'))
            logger.info("Recording resumed after audio playback")

async def monitor_speaking(voice_client, user_queues, text_channel, bot=None):
    """Monitor speaking events in voice channel"""
    logger.info("Monitor speaking started")
    while True:
        user, speaking = await voice_client.receiver.speaking.get()
        logger.info(f"Speaking event: User {user.id} speaking: {speaking}")
        
        if speaking and user not in user_queues:
            # User started speaking
            logger.info(f"User {user.id} started speaking, creating queue")
            audio_queue = queue.Queue()
            user_queues[user] = audio_queue
            
            # Get target language from bot settings
            target_lang = getattr(bot, 'target_language', 'Spanish') if bot else 'Spanish'
            
            # Start processing thread
            threading.Thread(
                target=process_user_audio,
                args=(user.id, audio_queue, text_channel, voice_client, target_lang, bot)
            ).start()
        elif not speaking and user in user_queues:
            # User stopped speaking
            logger.info(f"User {user.id} stopped speaking")
            user_queues[user].put(None)  # Signal thread to end
            del user_queues[user] 