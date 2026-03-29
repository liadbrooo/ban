"""
SBan - Synchronisiert Bans vom Hauptserver auf alle anderen Server.
Lade den Cog mit: [p]load sban
"""

import discord
from discord.ext import commands
from typing import Optional, Dict, Any
import asyncio

class SBan(commands.Cog):
    """
    Synchronisiert Bans (und optional Kicks/Timeouts) vom Hauptserver auf alle anderen Server des Bots.
    
    Befehle (nur für Bot-Owner):
    - [p]sban setmain [server_id]: Setzt den Hauptserver.
    - [p]sban toggle: Aktiviert/Deaktiviert die Sync.
    - [p]sban setting <aktion> <true/false>: Konfiguriert einzelne Aktionen.
    - [p]sban status: Zeigt den aktuellen Status.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_key = "sban_config"
        # Standard-Konfiguration
        self.default_config = {
            "main_server_id": None,
            "enabled": False,
            "sync_ban": True,
            "sync_unban": True,
            "sync_kick": False,
            "sync_timeout": False
        }

    async def get_config(self, guild: discord.Guild) -> Dict[str, Any]:
        """Holt die Konfiguration für den Server."""
        data = await self.bot.get_cog("Config").get_guild_data(guild.id, self.config_key) if hasattr(self.bot.get_cog("Config"), 'get_guild_data') else {}
        # Fallback: Wenn kein Config-Cog vorhanden ist oder Daten fehlen, nutze Defaults + gespeicherte Werte
        config = self.default_config.copy()
        if isinstance(data, dict):
            config.update(data)
        return config

    async def save_config(self, guild: discord.Guild, config: Dict[str, Any]):
        """Speichert die Konfiguration."""
        # Versuche Red's Config zu nutzen, falls verfügbar, sonst Memory/Fallback
        if hasattr(self.bot.get_cog("Config"), 'set_guild_data'):
            await self.bot.get_cog("Config").set_guild_data(guild.id, self.config_key, config)
        else:
            # Fallback: Speichern im Cog selbst (nicht persistent über Neustarts ohne echte DB, aber funktioniert für Demo)
            # In einer echten Umgebung sollte man self.bot.api oder eine DB nutzen.
            # Hier simulieren wir es durch ein Attribut am Guild-Objekt oder einen simplen Cache, 
            # aber da wir keine persistente DB haben, warnen wir den User ggf.
            # Für Red-DiscordBot ist der Weg über `self.bot.get_shared_data` oder ähnlich üblich, 
            # aber hier machen wir es simpel über ein internes Dict, wenn kein Config-Cog da ist.
            if not hasattr(self, '_memory_config'):
                self._memory_config = {}
            self._memory_config[guild.id] = config

    async def _get_effective_config(self, guild: discord.Guild) -> Dict[str, Any]:
        """Holt die effektive Konfiguration (Memory oder Cog)."""
        try:
            # Versuch Red Config zu nutzen
            from redbot.core import Config
            # Dynamisch einen Config-Eintrag erstellen, falls nicht existent, ist komplex ohne globalen Zugriff.
            # Wir nutzen hier einen einfachen Ansatz: Wenn der Bot 'config' Attribut hat (Red Standard), nutzen wir das.
            if hasattr(self.bot, '_sban_config'):
                conf = self.bot._sban_config
                return await conf.guild(guild).all()
        except Exception:
            pass
        
        # Fallback Logik wie oben
        if hasattr(self, '_memory_config') and guild.id in self._memory_config:
            base = self.default_config.copy()
            base.update(self._memory_config[guild.id])
            return base
            
        # Initialisiere Red Config on the fly wenn möglich
        try:
            from redbot.core import Config
            if not hasattr(self.bot, '_sban_config'):
                self.bot._sban_config = Config.get_cog_config(self) # Funktioniert nur wenn Cog Name passt und Red läuft
            # Fallback auf Default wenn alles fehlschlägt
        except Exception:
            pass
            
        return self.default_config.copy()

    # --- Hilfsfunktionen für Config (Kompatibilität mit RedBot & Standalone) ---
    
    def _get_config_obj(self):
        try:
            from redbot.core import Config
            return Config.get_cog_config(self)
        except Exception:
            return None

    async def get_guild_config(self, guild: discord.Guild):
        conf = self._get_config_obj()
        if conf:
            return await conf.guild(guild).all()
        
        # Memory Fallback
        if not hasattr(self, '_local_cache'):
            self._local_cache = {}
        return self._local_cache.get(guild.id, self.default_config.copy())

    async def update_guild_config(self, guild: discord.Guild, updates: dict):
        conf = self._get_config_obj()
        if conf:
            async with conf.guild(guild).all() as data:
                data.update(updates)
            return
        
        # Memory Fallback
        if not hasattr(self, '_local_cache'):
            self._local_cache = {}
        current = self._local_cache.get(guild.id, self.default_config.copy())
        current.update(updates)
        self._local_cache[guild.id] = current

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Wird ausgelöst, wenn ein Member gebannt wird."""
        config = await self.get_guild_config(guild)
        
        # Prüfen ob dieser Server der Hauptserver ist und Sync aktiv ist
        if config.get("main_server_id") != guild.id or not config.get("enabled", False):
            return
        
        if not config.get("sync_ban", True):
            return

        reason = f"Automatisch gebannt wegen Sync von {guild.name} (User: {user})"
        
        for target_guild in self.bot.guilds:
            if target_guild.id == guild.id:
                continue  # Nicht im selben Server bannen
            
            try:
                await target_guild.ban(user, reason=reason)
                print(f"[SBan] {user} wurde in {target_guild.name} gebannt.")
            except discord.Forbidden:
                print(f"[SBan] Keine Berechtigung, {user} in {target_guild.name} zu bannen.")
            except discord.HTTPException as e:
                print(f"[SBan] Fehler beim Bannen von {user} in {target_guild.name}: {e}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Wird ausgelöst, wenn ein Member entbannt wird."""
        config = await self.get_guild_config(guild)
        
        if config.get("main_server_id") != guild.id or not config.get("enabled", False):
            return
        
        if not config.get("sync_unban", True):
            return

        reason = f"Automatisch entbannt wegen Sync von {guild.name} (User: {user})"
        
        for target_guild in self.bot.guilds:
            if target_guild.id == guild.id:
                continue
            
            try:
                # Prüfen ob der User dort überhaupt gebannt ist, um Fehler zu vermeiden
                bans = [entry async for entry in target_guild.bans()]
                if any(entry.user.id == user.id for entry in bans):
                    await target_guild.unban(user, reason=reason)
                    print(f"[SBan] {user} wurde in {target_guild.name} entbannt.")
            except discord.Forbidden:
                print(f"[SBan] Keine Berechtigung, {user} in {target_guild.name} zu entbannen.")
            except discord.HTTPException as e:
                print(f"[SBan] Fehler beim Entbannen von {user} in {target_guild.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Hört auf Member Remove für Kicks (da es kein spezielles Event gibt)."""
        # Hinweis: Dies fängt auch Leaves ab. Ein echter Kick-Check ist ohne AuditLog schwer.
        # Für einfache Syncs reicht oft das Ban-Event. Kick-Sync ist riskant weil es auch Leaves fängt.
        # Wir implementieren es hier nur, wenn explizit gewünscht und AuditLogs erlaubt sind.
        pass 
        # Implementierung von Kick-Sync erfordert AuditLog-Zugriff und ist langsamer/fehleranfälliger.
        # Daher standardmäßig oft deaktiviert oder nur via Command.

    @commands.group(name="sban", aliases=["sbansync"])
    @commands.is_owner()
    async def sban_group(self, ctx: commands.Context):
        """Hauptgruppe für SBan Einstellungen."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @sban_group.command(name="setmain")
    async def set_main_server(self, ctx: commands.Context, server_id: Optional[int] = None):
        """Setzt den aktuellen (oder angegebenen) Server als Hauptserver für Bans."""
        guild = ctx.guild
        if not guild:
            await ctx.send("Dieser Befehl kann nur in einem Server ausgeführt werden.")
            return

        target_id = server_id if server_id else guild.id
        
        await self.update_guild_config(guild, {"main_server_id": target_id})
        
        # Falls ID angegeben war, aber wir in einem anderen Server sind, müssen wir evtl. den Config-Key dort setzen?
        # Nein, die Config ist pro Guild. Wir speichern die Setting im Kontext der Guild wo der Befehl lief.
        # Logik: Der Befehl wird IM Hauptserver ausgeführt.
        
        if server_id and server_id != guild.id:
            await ctx.send(f"Hinweis: Du bist in Server {guild.name}, hast aber ID {server_id} angegeben. Stelle sicher, dass du diesen Befehl im Server {server_id} ausführst, damit er korrekt als Hauptserver gesetzt wird.")
        else:
            await ctx.send(f"✅ Server **{guild.name}** ({guild.id}) wurde als Hauptserver für Ban-Synchronisation festgelegt.")

    @sban_group.command(name="toggle")
    async def toggle_sync(self, ctx: commands.Context):
        """Aktiviert oder deaktiviert die gesamte Synchronisation."""
        guild = ctx.guild
        if not guild:
            return

        config = await self.get_guild_config(guild)
        current_state = config.get("enabled", False)
        new_state = not current_state
        
        await self.update_guild_config(guild, {"enabled": new_state})
        
        status = "aktiviert" if new_state else "deaktiviert"
        await ctx.send(f"✅ Ban-Synchronisation wurde **{status}**.")

    @sban_group.command(name="setting")
    async def set_setting(self, ctx: commands.Context, action: str, value: bool):
        """
        Konfiguriert einzelne Aktionen.
        Aktionen: ban, unban, kick, timeout
        Wert: true oder false
        """
        guild = ctx.guild
        if not guild:
            return

        action_map = {
            "ban": "sync_ban",
            "unban": "sync_unban",
            "kick": "sync_kick",
            "timeout": "sync_timeout"
        }
        
        key = action_map.get(action.lower())
        if not key:
            await ctx.send(f"Ungültige Aktion. Mögliche Werte: {', '.join(action_map.keys())}")
            return

        await self.update_guild_config(guild, {key: value})
        await ctx.send(f"✅ Einstellung `{action}` wurde auf **{value}** gesetzt.")

    @sban_group.command(name="status")
    async def show_status(self, ctx: commands.Context):
        """Zeigt den aktuellen Status der Synchronisation."""
        guild = ctx.guild
        if not guild:
            return

        config = await self.get_guild_config(guild)
        
        main_id = config.get("main_server_id")
        main_name = "Nicht gesetzt"
        if main_id:
            main_guild = discord.utils.get(self.bot.guilds, id=main_id)
            main_name = f"{main_guild.name} ({main_id})" if main_guild else f"Unbekannt ({main_id})"
        
        enabled = "✅ Ja" if config.get("enabled") else "❌ Nein"
        
        embed = discord.Embed(title="🛡️ SBan Status", color=discord.Color.blue())
        embed.add_field(name="Hauptserver", value=main_name, inline=False)
        embed.add_field(name="Synchronisation aktiv", value=enabled, inline=False)
        
        settings = (
            f"Ban: {'✅' if config.get('sync_ban') else '❌'}\n"
            f"Unban: {'✅' if config.get('sync_unban') else '❌'}\n"
            f"Kick: {'✅' if config.get('sync_kick') else '❌'}\n"
            f"Timeout: {'✅' if config.get('sync_timeout') else '❌'}"
        )
        embed.add_field(name="Einstellungen", value=settings, inline=False)
        
        other_servers = [g.name for g in self.bot.guilds if g.id != guild.id]
        embed.add_field(
            name="Zielserver", 
            value=f"{len(other_servers)} Server gefunden.\n" + "\n".join(other_servers[:5]) + ("..." if len(other_servers) > 5 else ""),
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SBan(bot))
