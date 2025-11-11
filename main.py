from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os
import logging
from aiohttp import web
import asyncio

# Setup logging
logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)

# Get credentials from environment variables
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION')  # Your session string
PORT = int(os.environ.get('PORT', 8000))

# Get target chat IDs from environment variable
# Can be a single ID or multiple IDs separated by commas
CHAT_IDS_STR = os.environ.get('CHAT_IDS')
TARGET_CHAT_IDS = [int(chat_id.strip()) for chat_id in CHAT_IDS_STR.split(',')]

logging.info(f"Monitoring {len(TARGET_CHAT_IDS)} chat(s): {TARGET_CHAT_IDS}")

# Keywords to monitor (all variations of "می فروشم")
KEYWORDS = ['میفروشم', 'می‌فروشم', 'می فروشم']

# DM message to send
DM_MESSAGE = 'سلام، چه چیز هایی برای فروش داری'

# Create the client with StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Track users we've already messaged to avoid spam
messaged_users = set()

# Monitoring state (starts as False - bot won't monitor until you send !start)
is_monitoring = False

@client.on(events.NewMessage(outgoing=True, pattern=r'^!start$'))
async def start_monitoring(event):
    """Start monitoring when you send !start"""
    global is_monitoring
    is_monitoring = True
    await event.edit('✅ **Bot Started!** Monitoring is now active.')
    logging.info("Monitoring started by user command")

@client.on(events.NewMessage(outgoing=True, pattern=r'^!stop$'))
async def stop_monitoring(event):
    """Stop monitoring when you send !stop"""
    global is_monitoring
    is_monitoring = False
    await event.edit('⛔ **Bot Stopped!** Monitoring is now paused.')
    logging.info("Monitoring stopped by user command")

@client.on(events.NewMessage(outgoing=True, pattern=r'^!status$'))
async def check_status(event):
    """Check bot status when you send !status"""
    status = "✅ **Active**" if is_monitoring else "⛔ **Paused**"
    
    # Format chat IDs
    chats_list = '\n'.join([f"  • `{chat_id}`" for chat_id in TARGET_CHAT_IDS])
    
    msg = f"""
📊 **Bot Status:**
{status}

👥 Users messaged this session: {len(messaged_users)}
🎯 Monitoring {len(TARGET_CHAT_IDS)} chat(s):
{chats_list}

**Commands:**
• !start - Start monitoring
• !stop - Stop monitoring
• !status - Show this status
• !clear - Clear messaged users list
"""
    await event.edit(msg)

@client.on(events.NewMessage(outgoing=True, pattern=r'^!clear$'))
async def clear_users(event):
    """Clear the list of messaged users"""
    global messaged_users
    count = len(messaged_users)
    messaged_users.clear()
    await event.edit(f'🗑️ Cleared {count} users from the messaged list.')
    logging.info(f"Cleared {count} users from messaged list")

@client.on(events.NewMessage(chats=TARGET_CHAT_IDS))
async def handler(event):
    """Handle new messages in the target groups"""
    # Skip if monitoring is disabled
    if not is_monitoring:
        return
    
    try:
        # Get the message text
        message_text = event.message.text
        
        if not message_text:
            return
        
        # Check if any keyword is in the message
        message_lower = message_text.lower()
        if any(keyword in message_lower for keyword in KEYWORDS):
            # Get the sender
            sender = await event.get_sender()
            
            # Skip if it's a bot or if we've already messaged this user
            if sender.bot or sender.id in messaged_users:
                return
            
            # Get chat info
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', f'Chat {event.chat_id}')
            
            # Send DM to the user
            try:
                await client.send_message(sender, DM_MESSAGE)
                messaged_users.add(sender.id)
                logging.info(f"Sent DM to user {sender.id} ({sender.first_name}) from chat {chat_title}")
                
                # Send confirmation to yourself (in Saved Messages)
                me = await client.get_me()
                await client.send_message(
                    me.id,
                    f"✉️ Sent DM to [{sender.first_name}](tg://user?id={sender.id})\n📍 From: **{chat_title}**\n🔑 Keyword detected"
                )
            except Exception as e:
                logging.error(f"Failed to send DM to user {sender.id}: {e}")
                
    except Exception as e:
        logging.error(f"Error handling message: {e}")

# Health check web server
async def health_check(request):
    status = "active" if is_monitoring else "paused"
    return web.Response(text=f'Bot is running! Status: {status}')

async def start_web_server():
    """Start a simple web server for health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

async def main():
    """Start the bot"""
    # Start web server for Koyeb health checks
    await start_web_server()
    
    # Start Telegram client (no phone needed with session string)
    await client.start()
    logging.info("User bot started (monitoring paused - send !start to begin)")
    
    # Get info about the bot user
    me = await client.get_me()
    logging.info(f"Logged in as: {me.first_name} (@{me.username})")
    
    # Send startup message to yourself
    await client.send_message(
        me.id,
        """
🤖 **Bot Started Successfully!**

The bot is ready but monitoring is **paused**.

**Commands:**
• `!start` - Start monitoring
• `!stop` - Stop monitoring  
• `!status` - Check status
• `!clear` - Clear messaged users

Send `!start` to begin monitoring.
"""
    )
    
    # Keep the bot running
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
