import discord
import logging
from discord.ext import commands
from audio_processing import TranslationSink
from api_services import (
    get_elevenlabs_voices, assign_voice_to_user,
    get_user_input_language, get_user_output_language,
    set_user_input_language, set_user_output_language,
    load_voice_assignments
)

# Setup logging
logger = logging.getLogger(__name__)

class TranslatorBot(commands.Bot):
    def __init__(self, command_prefix='!'):
        # Initialize Discord bot with voice intents
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        
        super().__init__(command_prefix=command_prefix, intents=intents)
        
        # Default target language
        self.target_language = "Spanish"
        # Dictionary to store user input languages
        self.user_input_languages = {}
        
        # Register commands
        self.add_commands()
        
    def add_commands(self):
        """Add bot commands"""
        
        @self.command()
        async def join(ctx):
            """Join a voice channel and start translating"""
            # Check if already in a voice channel
            if ctx.voice_client:
                await ctx.send('I am already in a voice channel. Use !leave first.')
                return
                
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                try:
                    logger.info(f"Attempting to join voice channel: {channel}")
                    voice_client = await channel.connect()
                    
                    # Store the original text channel where the command was issued
                    voice_client.original_text_channel = ctx.channel
                    voice_client.bot = self
                    logger.info(f"Original text channel set to: {ctx.channel.name}")
                    
                    # Start recording
                    user_queues = {}
                    sink = TranslationSink(user_queues)
                    
                    # Store references to important objects in the sink
                    sink.text_channel = ctx.channel
                    sink.voice_client = voice_client
                    sink.bot = self
                    
                    # Store sink reference in voice_client for reuse later
                    voice_client.last_sink = sink
                    
                    # Start recording with the correct callback format
                    voice_client.start_recording(sink, lambda: logger.info('Recording ended'))
                    logger.info("Recording started")
                    
                    # Store user_queues in voice_client for reference elsewhere
                    voice_client.user_queues = user_queues
                    
                    await ctx.send(f'Joined {channel} and started translating. Speak clearly to test.')
                except Exception as e:
                    logger.error(f"Error joining channel: {e}")
                    await ctx.send(f'Error joining voice channel: {str(e)}')
            else:
                await ctx.send('You need to be in a voice channel first.')

        @self.command()
        async def leave(ctx):
            """Leave the voice channel"""
            if ctx.voice_client:
                ctx.voice_client.stop_recording()
                await ctx.voice_client.disconnect()
                await ctx.send('Left the voice channel.')
            else:
                await ctx.send('I am not in a voice channel.')

        @self.command()
        async def setlang(ctx, language):
            """Set the target translation language (both global and personal)"""
            # Update bot's global default
            self.target_language = language
            
            # Also update this user's output language
            user_id = ctx.author.id
            set_user_output_language(user_id, language)
            
            await ctx.send(f"Target language set to {language} (globally and for your personal output)")

        @self.command()
        async def languages(ctx):
            """List common available languages"""
            common_languages = [
                "Spanish", "French", "German", "Italian", "Portuguese", 
                "Russian", "Japanese", "Chinese", "Korean", "Arabic",
                "Hindi", "Dutch", "Swedish", "Greek", "Turkish"
            ]
            await ctx.send("Common available languages:\n" + "\n".join(common_languages))
            await ctx.send("You can try other languages as well - Mistral supports many languages.")

        @self.command()
        async def info(ctx):
            """Show information about the bot"""
            info_message = (
                f"**Discord Voice Translator**\n"
                f"- Global Default Target Language: {self.target_language}\n"
                f"- Speech Recognition: ElevenLabs\n"
                f"- Translation: Mistral AI\n"
                f"- Text-to-Speech: ElevenLabs\n\n"
                f"**Commands**\n"
                f"- `!join` - Join your voice channel and start translating\n"
                f"- `!leave` - Leave the voice channel\n"
                f"- `!setlang [language]` - Set target language (global default and your output)\n"
                f"- `!input [language]` - Set your source language\n"
                f"- `!output [language]` - Set your output language\n"
                f"- `!setvoice [number]` - Set your TTS voice\n"
                f"- `!myconfig` - View your language settings\n"
                f"- `!languages` - List available languages\n"
                f"- `!info` - Show this information"
            )
            
            await ctx.send(info_message)

        @self.command()
        async def ping(ctx):
            """Simple ping command to check if bot is responsive"""
            await ctx.send('Pong!')

        @self.command()
        async def input(ctx, language):
            """Set the source language for the user"""
            user_id = ctx.author.id
            set_user_input_language(user_id, language)
            await ctx.send(f"Your input language has been set to {language}")

        @self.command()
        async def output(ctx, language):
            """Set the output language for the user"""
            user_id = ctx.author.id
            set_user_output_language(user_id, language)
            await ctx.send(f"Your output language has been set to {language}")

        @self.command()
        async def myconfig(ctx):
            """Show a user's current language settings"""
            user_id = ctx.author.id
            
            # Get language preferences
            input_lang = get_user_input_language(user_id, default="English")
            output_lang = get_user_output_language(user_id, default=self.target_language)
            
            # Get voice information
            voice_name = "Default"
            voice_index = "N/A"
            
            assignments = load_voice_assignments()
            voices = get_elevenlabs_voices()
            
            if str(user_id) in assignments:
                voice_id = assignments[str(user_id)]
                for i, voice in enumerate(voices):
                    if voice.get("voice_id") == voice_id:
                        voice_name = voice.get("name", "Unknown")
                        voice_index = i + 1  # Convert to 1-based index for display
                        break
            
            await ctx.send(f"Your settings:\n- Input language: {input_lang}\n- Output language: {output_lang}\n- Voice: {voice_name} (#{voice_index})")

        @self.command()
        async def setvoice(ctx, voice_index=None):
            """Set the user's TTS voice by index"""
            user_id = ctx.author.id
            
            # Get available voices
            voices = get_elevenlabs_voices()
            if not voices:
                await ctx.send("Could not fetch available voices. Please check if voices.json exists and is valid.")
                return
            
            # If no index provided, list available voices
            if voice_index is None:
                voice_list = ""
                for i, voice in enumerate(voices):
                    voice_list += f"{i+1}. {voice.get('name', 'Unknown')}\n"
                
                # Create embed with voice list
                embed = discord.Embed(title="Available Voices", 
                                     description="Use `!setvoice [number]` to select a voice.",
                                     color=0x00ff00)
                embed.add_field(name="Voice Options", value=voice_list, inline=False)
                
                await ctx.send(embed=embed)
                return
            
            # Try to convert input to integer
            try:
                index = int(voice_index) - 1  # Convert to 0-based index
                
                # Check if index is valid
                if index < 0 or index >= len(voices):
                    await ctx.send(f"Invalid voice number. Please choose a number between 1 and {len(voices)}.")
                    return
                
                # Get the selected voice
                selected_voice = voices[index]
                voice_id = selected_voice.get("voice_id")
                voice_name = selected_voice.get("name")
                
                # Assign the voice to the user
                assign_voice_to_user(user_id, voice_id)
                
                await ctx.send(f"Your voice has been set to {voice_name}!")
                
            except ValueError:
                await ctx.send("Please provide a valid number for the voice selection.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'Bot is ready! Logged in as {self.user}')
        logger.info(f'Bot ID: {self.user.id}')
        logger.info(f'Opus loaded: {discord.opus.is_loaded()}')
        logger.info(f'Use !join in a Discord server to start translating')

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command not found. Try `!info` for available commands.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send(f"Error: {error}")
