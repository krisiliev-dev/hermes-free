import os, sys
sys.path.insert(0, '/Users/kristiyaniliev/.hermes/hermes-agent')
os.chdir('/Users/kristiyaniliev/.hermes/hermes-agent')
import asyncio
from plugins.platforms.discord.adapter import DiscordAdapter

async def main():
    adapter = DiscordAdapter.__new__(DiscordAdapter)
    await adapter.connect()
    try:
        print('BOT_USER', adapter._client.user.id, adapter._client.user)
        for g in adapter._client.guilds:
            print('GUILD', g.id, getattr(g, 'name', None), 'channels', len(getattr(g, 'channels', [])))
            for ch in getattr(g, 'channels', []):
                try:
                    print('  CHANNEL', ch.id, type(ch).__name__, getattr(ch, 'name', None), 'nsfw=', getattr(ch, 'nsfw', None))
                except Exception as e:
                    print('  CHANNEL_ERR', e)
            for cid, st in adapter._voice_clients.items():
                print('  VOICE_CLIENT', cid, st.channel.id if st.channel else None, getattr(st.channel, 'name', None))
    finally:
        try:
            await adapter._client.close()
        except Exception:
            pass

asyncio.run(main())
