import discord
from redbot.core import commands, checks, Config
from redbot.core.bot import Red
from typing import Optional, List
import logging

log = logging.getLogger("red.sban")

class SBan(commands.Cog):
    """Synchronisiert Bans vom Hauptserver automatisch auf alle anderen Server."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8765432109, force_registration=True)
        
        default_global = {
            "main_guild_id": None,
            "enabled": False,
            "sync_ban": True,
            "sync_unban": True,
            "sync_kick": False,
            "sync_timeout": False
        }
        self.config.register_global(**default_global)

    async def cog_load(self):
        """Wird beim Laden des Cogs ausgeführt."""
        log.info("SBan Cog wurde geladen.")

    async def cog_unload(self):
        """Wird beim Entladen des Cogs ausgeführt."""
        log.info("SBan Cog wurde entladen.")

    async def is_main_guild(self, guild_id: int) -> bool:
        """Prüft ob eine Guild-ID dem Hauptserver entspricht."""
        main_id = await self.config.main_guild_id()
        return main_id is not None and guild_id == main_id

    async def get_target_guilds(self, exclude_guild_id: int) -> List[discord.Guild]:
        """Gibt alle Server zurück, außer dem angegebenen."""
        return [g for g in self.bot.guilds if g.id != exclude_guild_id]

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Wird ausgelöst, wenn ein User gebannt wird."""
        # Prüfen ob dies der Hauptserver ist
        if not await self.is_main_guild(guild.id):
            return
        
        # Prüfen ob Sync aktiviert ist
        enabled = await self.config.enabled()
        if not enabled:
            return
            
        sync_ban = await self.config.sync_ban()
        if not sync_ban:
            return

        log.info(f"Ban erkannt auf {guild.name} für {user} (ID: {user.id}). Starte Synchronisation...")
        await self._execute_sync_ban(guild, user)

    async def _execute_sync_ban(self, source_guild: discord.Guild, user: discord.User):
        """Führt den Ban auf allen Ziel-Servern aus."""
        target_guilds = await self.get_target_guilds(source_guild.id)
        
        if not target_guilds:
            log.warning("Keine Ziel-Server für Synchronisation gefunden.")
            return

        success_count = 0
        fail_count = 0
        
        for target_guild in target_guilds:
            try:
                # Prüfen ob der User bereits gebannt ist
                ban_list = await target_guild.bans()
                is_banned = any(ban.user.id == user.id for ban in ban_list)
                
                if is_banned:
                    log.debug(f"User {user.id} ist bereits gebannt auf {target_guild.name}")
                    continue
                
                # Ban ausführen
                await target_guild.ban(
                    user, 
                    reason=f"🔄 Auto-Sync-Ban von {source_guild.name} | User: {user} (ID: {user.id})"
                )
                success_count += 1
                log.info(f"✅ Ban synchronisiert auf {target_guild.name} für {user}")
                
            except discord.Forbidden:
                fail_count += 1
                log.error(f"❌ Keine Berechtigung zum Bannen auf {target_guild.name}")
            except discord.HTTPException as e:
                fail_count += 1
                log.error(f"❌ HTTP-Fehler beim Bannen auf {target_guild.name}: {e}")
            except Exception as e:
                fail_count += 1
                log.error(f"❌ Unbekannter Fehler beim Bannen auf {target_guild.name}: {type(e).__name__}: {e}")

        log.info(f"Synchronisation abgeschlossen: {success_count} erfolgreich, {fail_count} fehlgeschlagen")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Wird ausgelöst, wenn ein User entbannt wird."""
        # Prüfen ob dies der Hauptserver ist
        if not await self.is_main_guild(guild.id):
            return
        
        # Prüfen ob Sync aktiviert ist
        enabled = await self.config.enabled()
        if not enabled:
            return
            
        sync_unban = await self.config.sync_unban()
        if not sync_unban:
            return

        log.info(f"Unban erkannt auf {guild.name} für {user} (ID: {user.id}). Starte Synchronisation...")
        await self._execute_sync_unban(guild, user)

    async def _execute_sync_unban(self, source_guild: discord.Guild, user: discord.User):
        """Führt den Unban auf allen Ziel-Servern aus."""
        target_guilds = await self.get_target_guilds(source_guild.id)
        
        if not target_guilds:
            log.warning("Keine Ziel-Server für Synchronisation gefunden.")
            return

        success_count = 0
        fail_count = 0
        
        for target_guild in target_guilds:
            try:
                # Unban ausführen (discord wirft keine Exception wenn nicht gebannt bei unban mit User-Objekt)
                await target_guild.unban(
                    user, 
                    reason=f"🔄 Auto-Sync-Unban von {source_guild.name} | User: {user} (ID: {user.id})"
                )
                success_count += 1
                log.info(f"✅ Unban synchronisiert auf {target_guild.name} für {user}")
                
            except discord.NotFound:
                # User war auf diesem Server nicht gebannt
                log.debug(f"User {user.id} war auf {target_guild.name} nicht gebannt")
                continue
            except discord.Forbidden:
                fail_count += 1
                log.error(f"❌ Keine Berechtigung zum Entbannen auf {target_guild.name}")
            except discord.HTTPException as e:
                fail_count += 1
                log.error(f"❌ HTTP-Fehler beim Entbannen auf {target_guild.name}: {e}")
            except Exception as e:
                fail_count += 1
                log.error(f"❌ Unbekannter Fehler beim Entbannen auf {target_guild.name}: {type(e).__name__}: {e}")

        log.info(f"Unban-Synchronisation abgeschlossen: {success_count} erfolgreich, {fail_count} fehlgeschlagen")

    @commands.group(name="sban", aliases=["sb"])
    @checks.is_owner()
    async def sban_group(self, ctx: commands.Context):
        """Hauptgruppe für SBan-Konfiguration."""
        pass

    @sban_group.command(name="setmain")
    async def set_main_server(self, ctx: commands.Context):
        """Setzt den aktuellen Server als Hauptserver für Bans."""
        await self.config.main_guild_id.set(ctx.guild.id)
        await ctx.send(f"✅ Dieser Server ({ctx.guild.name}) ist jetzt der Hauptserver. Bans von hier werden synchronisiert.")

    @sban_group.command(name="toggle")
    async def toggle_sync(self, ctx: commands.Context):
        """Aktiviert oder deaktiviert die gesamte Synchronisation."""
        current = await self.config.enabled()
        await self.config.enabled.set(not current)
        status = "aktiviert" if not current else "deaktiviert"
        await ctx.send(f"🔄 Ban-Synchronisation wurde {status}.")

    @sban_group.command(name="setting")
    async def set_setting(self, ctx: commands.Context, action: str, value: bool):
        """
        Konfiguriert einzelne Aktionen.
        Aktionen: ban, unban, kick, timeout
        Wert: true oder false
        """
        action = action.lower()
        valid_actions = ["ban", "unban", "kick", "timeout"]
        
        if action not in valid_actions:
            await ctx.send(f"❌ Ungültige Aktion. Wähle aus: {', '.join(valid_actions)}")
            return

        config_attr = f"sync_{action}"
        await getattr(self.config, config_attr).set(value)
        await ctx.send(f"✅ Synchronisation für **{action}** wurde auf `{value}` gesetzt.")

    @sban_group.command(name="status")
    async def show_status(self, ctx: commands.Context):
        """Zeigt den aktuellen Status der Synchronisation."""
        main_id = await self.config.main_guild_id()
        enabled = await self.config.enabled()
        
        main_name = "Nicht gesetzt"
        if main_id:
            guild = self.bot.get_guild(main_id)
            main_name = guild.name if guild else f"ID: {main_id} (nicht gefunden)"

        ban_sync = await self.config.sync_ban()
        unban_sync = await self.config.sync_unban()
        kick_sync = await self.config.sync_kick()
        timeout_sync = await self.config.sync_timeout()

        total_servers = len(self.bot.guilds)
        target_servers = total_servers - 1 if main_id else 0

        embed = discord.Embed(title="🛡️ SBan Status", color=discord.Color.blue())
        embed.add_field(name="Status", value="🟢 Aktiv" if enabled else "🔴 Inaktiv")
        embed.add_field(name="Hauptserver", value=main_name)
        embed.add_field(name="Ziel-Server", value=str(target_servers))
        
        embed.add_field(name="Einstellungen", value=(
            f"**Ban:** {'✅' if ban_sync else '❌'}\n"
            f"**Unban:** {'✅' if unban_sync else '❌'}\n"
            f"**Kick:** {'✅' if kick_sync else '❌'}\n"
            f"**Timeout:** {'✅' if timeout_sync else '❌'}"
        ), inline=False)
        
        await ctx.send(embed=embed)

    @sban_group.command(name="info")
    async def show_info(self, ctx: commands.Context):
        """Zeigt Informationen zur Nutzung."""
        text = (
            "**So funktioniert SBan:**\n"
            "1. Setze diesen Server als Hauptserver mit `sban setmain`.\n"
            "2. Aktiviere die Sync mit `sban toggle`.\n"
            "3. Jeder Ban, der auf diesem Server ausgeführt wird (durch Mods/Bots), "
            "wird automatisch auf allen anderen Servern wiederholt.\n\n"
            "Du kannst mit `sban setting <aktion> true/false` steuern, was synchronisiert wird."
        )
        await ctx.send(text)


async def setup(bot: Red):
    """Lädt den SBan Cog."""
    cog = SBan(bot)
    await bot.add_cog(cog)
    log.info("SBan Cog erfolgreich geladen.")
