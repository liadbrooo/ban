"""
Ban Synchronisation Cog für RedBot
Synchronisiert Bans, Unbans, Kicks und Timeouts zwischen allen Servern
"""

import discord
from redbot.core import commands, checks, Config
from redbot.core.bot import Red
from typing import Optional
import asyncio


class BanSync(commands.Cog):
    """
    Synchronisiert Moderationsaktionen (Ban, Unban, Kick, Timeout) 
    von einem Hauptserver auf alle anderen Server des Bots.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        
        default_global = {
            "main_server_id": None,
            "sync_enabled": False,
            "sync_ban": True,
            "sync_unban": True,
            "sync_kick": True,
            "sync_timeout": True,
        }
        
        self.config.register_global(**default_global)

    @commands.group(name="bansync", aliases=["bansynchro", "bsync"])
    @commands.is_owner()
    async def bansync_group(self, ctx: commands.Context):
        """
        Hauptbefehl für die Ban-Synchronisation Einstellungen.
        Nur für Bot-Owner verfügbar.
        """
        pass

    @bansync_group.command(name="setmain")
    async def bansync_setmain(self, ctx: commands.Context, server_id: Optional[int] = None):
        """
        Setzt den Hauptserver für die Ban-Synchronisation.
        
        Wenn keine Server-ID angegeben wird, wird der aktuelle Server verwendet.
        Alle Bans von diesem Server werden auf alle anderen synchronisiert.
        
        Beispiel:
        [p]bansync setmain 123456789012345678
        [p]bansync setmain (im Hauptserver)
        """
        if server_id is None:
            server_id = ctx.guild.id
        
        try:
            main_server = self.bot.get_guild(server_id)
            if main_server is None:
                await ctx.send("❌ Der angegebene Server wurde nicht gefunden. Ist der Bot darauf?")
                return
            
            await self.config.main_server_id.set(server_id)
            await ctx.send(
                f"✅ **Hauptserver gesetzt!**\n\n"
                f"📋 Server: **{main_server.name}**\n"
                f"🆔 ID: `{server_id}`\n\n"
                f"Alle Moderationsaktionen von diesem Server werden nun synchronisiert."
            )
        except Exception as e:
            await ctx.send(f"❌ Fehler beim Setzen des Hauptservers: {str(e)}")

    @bansync_group.command(name="toggle")
    async def bansync_toggle(self, ctx: commands.Context):
        """
        Aktiviert oder deaktiviert die gesamte Ban-Synchronisation.
        """
        current_state = await self.config.sync_enabled()
        new_state = not current_state
        
        await self.config.sync_enabled.set(new_state)
        
        status = "🟢 **aktiviert**" if new_state else "🔴 **deaktiviert**"
        await ctx.send(f"Ban-Synchronisation wurde {status}.")

    @bansync_group.command(name="setting")
    async def bansync_setting(self, ctx: commands.Context, action: str, enabled: bool):
        """
        Konfiguriert welche Aktionen synchronisiert werden sollen.
        
        Aktionen: `ban`, `unban`, `kick`, `timeout`
        
        Beispiel:
        [p]bansync setting ban true
        [p]bansync setting timeout false
        """
        action = action.lower()
        valid_actions = ["ban", "unban", "kick", "timeout"]
        
        if action not in valid_actions:
            await ctx.send(
                f"❌ Ungültige Aktion. Gültige Optionen: {', '.join(valid_actions)}"
            )
            return
        
        config_key = f"sync_{action}"
        await self.config.set_raw(config_key, value=enabled)
        
        emoji = "✅" if enabled else "❌"
        action_display = action.capitalize()
        await ctx.send(f"{emoji} Synchronisation für **{action_display}** wurde {'aktiviert' if enabled else 'deaktiviert'}.")

    @bansync_group.command(name="status")
    async def bansync_status(self, ctx: commands.Context):
        """
        Zeigt den aktuellen Status der Ban-Synchronisation an.
        """
        main_server_id = await self.config.main_server_id()
        sync_enabled = await self.config.sync_enabled()
        sync_ban = await self.config.sync_ban()
        sync_unban = await self.config.sync_unban()
        sync_kick = await self.config.sync_kick()
        sync_timeout = await self.config.sync_timeout()
        
        main_server = self.bot.get_guild(main_server_id) if main_server_id else None
        
        embed = discord.Embed(
            title="🔄 Ban-Synchronisation Status",
            color=discord.Color.blue() if sync_enabled else discord.Color.red()
        )
        
        embed.add_field(
            name="📊 Gesamtstatus",
            value=f"{'🟢 Aktiviert' if sync_enabled else '🔴 Deaktiviert'}",
            inline=False
        )
        
        embed.add_field(
            name="🏠 Hauptserver",
            value=f"**{main_server.name}**\n`{main_server_id}`" if main_server else "❌ Nicht gesetzt",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Einstellungen",
            value=(
                f"{'✅' if sync_ban else '❌'} Ban\n"
                f"{'✅' if sync_unban else '❌'} Unban\n"
                f"{'✅' if sync_kick else '❌'} Kick\n"
                f"{'✅' if sync_timeout else '❌'} Timeout"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📈 Statistiken",
            value=f"{len(self.bot.guilds)} Server insgesamt",
            inline=True
        )
        
        embed.set_footer(text="Nur der Bot-Owner kann diese Einstellungen ändern.")
        await ctx.send(embed=embed)

    @bansync_group.command(name="info")
    async def bansync_info(self, ctx: commands.Context):
        """
        Zeigt Informationen über die Ban-Synchronisation.
        """
        embed = discord.Embed(
            title="ℹ️ Ban-Synchronisation Info",
            description="Dieser Cog synchronisiert Moderationsaktionen von einem Hauptserver auf alle anderen Server.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎯 Funktionsweise",
            value=(
                "Wenn ein Benutzer auf dem **Hauptserver** gebannt, entbannt, "
                "gekickt oder getimeoutet wird, wird dieselbe Aktion automatisch "
                "auf **allen anderen Servern** ausgeführt."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📝 Befehle",
            value=(
                "`[p]bansync setmain [server_id]` - Hauptserver setzen\n"
                "`[p]bansync toggle` - Synchronisation ein/ausschalten\n"
                "`[p]bansync setting <aktion> <true/false>` - Aktionen konfigurieren\n"
                "`[p]bansync status` - Status anzeigen\n"
                "`[p]bansync info` - Diese Hilfe"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Wichtig",
            value=(
                "• Nur der Bot-Owner kann Einstellungen ändern\n"
                "• Der Standard-Ban-Befehl bleibt erhalten\n"
                "• Aktionen werden nur vom Hauptserver synchronisiert"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    async def sync_to_other_servers(self, main_guild: discord.Guild, user: discord.User, action: str, reason: Optional[str] = None, duration: Optional[int] = None):
        """
        Synchronisiert eine Aktion zu allen anderen Servern.
        """
        sync_enabled = await self.config.sync_enabled()
        if not sync_enabled:
            return
        
        action_config = f"sync_{action}"
        sync_action = await self.config.raw.get(action_config, True)
        if not sync_action:
            return
        
        target_servers = [g for g in self.bot.guilds if g.id != main_guild.id]
        
        results = {"success": 0, "failed": 0, "already": 0}
        
        for guild in target_servers:
            try:
                member = guild.get_member(user.id)
                if member is None:
                    continue
                
                bot_member = guild.me
                if not bot_member.guild_permissions.administrator:
                    results["failed"] += 1
                    continue
                
                if action == "ban":
                    try:
                        await guild.ban(user, reason=reason or f"Sync-Ban von {main_guild.name}")
                        results["success"] += 1
                    except discord.errors.Forbidden:
                        results["failed"] += 1
                    except discord.errors.HTTPException as e:
                        if "Unknown User" in str(e) or e.code == 10013:
                            results["already"] += 1
                        else:
                            results["failed"] += 1
                
                elif action == "unban":
                    try:
                        await guild.unban(user, reason=reason or f"Sync-Unban von {main_guild.name}")
                        results["success"] += 1
                    except discord.errors.NotFound:
                        results["already"] += 1
                    except discord.errors.Forbidden:
                        results["failed"] += 1
                
                elif action == "kick":
                    try:
                        await member.kick(reason=reason or f"Sync-Kick von {main_guild.name}")
                        results["success"] += 1
                    except discord.errors.Forbidden:
                        results["failed"] += 1
                
                elif action == "timeout":
                    try:
                        until = discord.utils.utcnow() + discord.utils.timedelta(seconds=duration) if duration else None
                        await member.timeout(until, reason=reason or f"Sync-Timeout von {main_guild.name}")
                        results["success"] += 1
                    except discord.errors.Forbidden:
                        results["failed"] += 1
                
            except Exception:
                results["failed"] += 1
                continue
        
        return results

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """
        Listener für Ban-Events.
        """
        main_server_id = await self.config.main_server_id()
        if main_server_id is None or guild.id != main_server_id:
            return
        
        await self.sync_to_other_servers(guild, user, "ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """
        Listener für Unban-Events.
        """
        main_server_id = await self.config.main_server_id()
        if main_server_id is None or guild.id != main_server_id:
            return
        
        await self.sync_to_other_servers(guild, user, "unban")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """
        Listener für Kick-Events (Member Remove ohne Ban).
        """
        main_server_id = await self.config.main_server_id()
        if main_server_id is None or member.guild.id != main_server_id:
            return
        
        # Prüfen ob es ein Kick war (nicht durch Ban)
        # Wir können nicht direkt unterscheiden, aber wir können prüfen ob der User gebannt ist
        try:
            ban_entry = await member.guild.bans().find(lambda b: b.user.id == member.id)
            if ban_entry is None:
                # Es war wahrscheinlich ein Kick
                await self.sync_to_other_servers(member.guild, member.user, "kick")
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Listener für Timeout-Events.
        """
        main_server_id = await self.config.main_server_id()
        if main_server_id is None or before.guild.id != main_server_id:
            return
        
        # Prüfen ob Timeout geändert wurde
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until is not None:
                # Timeout wurde gesetzt
                duration = int((after.timed_out_until - discord.utils.utcnow()).total_seconds())
                if duration > 0:
                    await self.sync_to_other_servers(before.guild, after.user, "timeout", duration=duration)

    def cog_unload(self):
        """Wird aufgerufen wenn der Cog entladen wird."""
        pass


async def setup(bot: Red):
    """Lädt den Cog."""
    await bot.add_cog(BanSync(bot))
