# Discord Voice Translator Bot

A Discord bot that translates spoken English to other languages in real-time. The bot listens to voice chat, transcribes the audio, translates it, and plays back the translation as speech.

## Features

- Real-time voice translation
- Support for multiple languages
- Text output of both original and translated speech
- Easy-to-use commands
- Configurable target language

## Prerequisites

- Python 3.13 or higher
- Discord Bot Token
- ElevenLabs API Key (for speech features)
- Mistral AI API Key (for translation)
- FFmpeg installed on your system
- Opus library (automatically handled for most systems)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/wesleyttt/cs153-project.git
cd cs153-project
```

2. Create and activate Conda environment:

```bash
conda env create -f local_env.yml
conda activate discord_bot
```

3. Copy `example.env` to `.env` and fill in your credentials:

```plaintext
DISCORD_TOKEN=your_discord_token
ELEVENLABS_API_KEY=your_elevenlabs_key
MISTRAL_API_KEY=your_mistral_key
```


## Bot Commands

- `!help` - Show a list of available commands
- `!join` - Join your voice channel and start translating
- `!leave` - Leave the voice channel
- `!output [language]` - Set your target language (e.g., "Spanish", "French")
- `!input [language]` - Set your source language (e.g., "English", "Spanish")
- `!setvoice [voice_id]` - Set your voice (voice_id is an int between 1 and 20)
- `!myconfig` - View your current language settings
- `!languages` - List available languages
- `!info` - Show bot information
- `!ping` - Test if the bot is responsive

Deprecated commands:
- `!setlang [language]` - Set target language (e.g., "Spanish", "French")

## Usage

1. Invite the bot to your Discord server
2. Join a voice channel
3. Use `!join` to bring the bot into your channel
4. (Optional) Use `!input [language]` to set your input language
5. Start speaking in your chosen language
6. The bot will:
   - Transcribe your speech
   - Show the original text in the chat
   - Show the translation in the chat
   - Play the translated audio in the voice channel

## Common Languages Supported

- Spanish
- French
- German
- Italian
- Portuguese
- Russian
- Japanese
- Chinese
- Korean
- Arabic
- Hindi
- Dutch
- Swedish
- Greek
- Turkish

Additional languages may be supported through Mistral AI's translation capabilities.

## Troubleshooting

If voice features aren't working:
- Ensure FFmpeg is installed on your system
- Check that the Opus library is properly loaded
- Verify your ElevenLabs API key is valid
- Make sure the bot has proper permissions in your Discord server

For Opus-related issues:
- On macOS: Install Opus using Homebrew: `brew install opus`
- On Linux: Install using package manager: `sudo apt-get install libopus0`
- On Windows: The bot should handle Opus automatically

## Environment Variables

- `DISCORD_TOKEN` - Your Discord bot token
- `MISTRAL_API_KEY` - Mistral AI API key for translations
- `ELEVENLABS_API_KEY` - ElevenLabs API key for speech features
- `ELEVENLABS_VOICE_ID` - (Optional) Custom voice ID for text-to-speech

## Discord Bot Permissions

The bot requires the following permissions:
- View Channels
- Send Messages
- Connect to Voice Channel
- Speak in Voice Channel
- Use Voice Activity

You can generate an invite link with these permissions from the Discord Developer Portal.

## Development

To run the bot in development mode:

1. Ensure all prerequisites are installed
2. Activate your virtual environment
3. Run the bot:

```bash
python main.py
```


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## Acknowledgments

- Discord.py for the Discord API wrapper
- Mistral AI for translation services
- ElevenLabs for speech-to-text and text-to-speech capabilities

## Support

If you encounter any issues or have questions:
1. Check the Troubleshooting section above
2. Look through existing GitHub Issues
3. Create a new Issue with detailed information about your problem

## Security

Please do not commit any API keys or sensitive information. Always use environment variables or secure configuration files for sensitive data.
