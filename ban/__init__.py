"""Ban Synchronisation Package"""
from .bansync import BanSync

async def setup(bot):
    """Lädt den BanSync Cog."""
    from .bansync import setup as bansync_setup
    await bansync_setup(bot)
