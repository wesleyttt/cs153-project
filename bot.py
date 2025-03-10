import discord
import logging
from discord.ext import commands
from audio_processing import TranslationSink

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
            """Set the target translation language"""
            self.target_language = language
            await ctx.send(f"Target language set to {language}")

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
                f"- Target Language: {self.target_language}\n"
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

        @self.command()
        async def ping(ctx):
            """Simple ping command to check if bot is responsive"""
            await ctx.send('Pong!')

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
