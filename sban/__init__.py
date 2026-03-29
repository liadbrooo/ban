from .sban import SBan

__red_end_user_data_statement__ = "This cog stores user IDs for ban synchronization purposes."

async def setup(bot):
    """Setup-Funktion für den SBan Cog."""
    from redbot.core.bot import Red
    cog = SBan(bot)
    await bot.add_cog(cog)
