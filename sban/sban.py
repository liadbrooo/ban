import discord
from redbot.core import commands, checks, Config
from redbot.core.bot import Red
from typing import Optional

class SBan(commands.Cog):
    """Synchronisiert Bans vom Hauptserver auf alle anderen Server."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        
        default_global = {
            "main_guild_id": None,
            "enabled": False,
            "sync_ban": True,
            "sync_unban": False,
            "sync_kick": False,
            "sync_timeout": False
        }
        self.config.register_global(**default_global)

    async def cog_load(self):
        # Listener für Member-Bans registrieren
        self.bot.add_listener(self.on_member_ban, "on_member_ban")
        self.bot.add_listener(self.on_member_unban, "on_member_unban")
        # Hinweis: Kicks und Timeouts haben keine direkten Events in d.py, 
        # sie müssten über Audit-Logs oder manuelle Commands gehandhabt werden.
        # Für einfache Bans/Unbans reicht dies.

    async def cog_unload(self):
        self.bot.remove_listener(self.on_member_ban, "on_member_ban")
        self.bot.remove_listener(self.on_member_unban, "on_member_unban")

    async def sync_to_other_servers(self, member: discord.Member, action: str, reason: Optional[str] = None):
        """Führt eine Aktion auf allen anderen Servern aus."""
        main_guild_id = await self.config.main_guild_id()
        enabled = await self.config.enabled()
        
        if not enabled or not main_guild_id:
            return

        # Prüfen, ob die Aktion synchronisiert werden soll
        if action == "ban" and not await self.config.sync_ban():
            return
        if action == "unban" and not await self.config.sync_unban():
            return
        if action == "kick" and not await self.config.sync_kick():
            return
        if action == "timeout" and not await self.config.sync_timeout():
            return

        # Wenn das Event nicht vom Hauptserver kommt, ignorieren
        if member.guild.id != main_guild_id:
            return

        target_guilds = [g for g in self.bot.guilds if g.id != main_guild_id]
        
        for guild in target_guilds:
            try:
                # Versuchen, das Mitglied im Zielserver zu finden (für Unban/Kick/Timeout relevant)
                # Bei Ban ist das Mitglied evtl. schon nicht mehr da, wir brauchen nur die ID
                target_member = None
                try:
                    target_member = await guild.fetch_member(member.id)
                except discord.NotFound:
                    # Mitglied ist nicht auf dem Server (z.B. schon gebannt oder nie dabei)
                    if action == "unban" or action == "kick" or action == "timeout":
                        continue # Kann nicht gekickt/entbannt werden wenn nicht da
                    pass # Bei Ban können wir trotzdem bannen (falls er joinen würde)

                if action == "ban":
                    await guild.ban(discord.Object(id=member.id), reason=f"Synchronized Ban from {member.guild.name}: {reason}")
                elif action == "unban" and target_member is None:
                    # Wir versuchen es trotzdem mit der ID für den Fall, dass er gebannt ist
                    await guild.unban(discord.Object(id=member.id), reason=f"Synchronized Unban from {member.guild.name}")
                elif action == "kick" and target_member:
                    await target_member.kick(reason=f"Synchronized Kick from {member.guild.name}: {reason}")
                elif action == "timeout" and target_member:
                    # Timeout für 10 Sekunden als Beispiel, müsste angepasst werden wenn spezifische Dauer nötig
                    await target_member.timeout(discord.utils.utcnow(), reason=f"Synchronized Timeout from {member.guild.name}")
                    
            except discord.Forbidden:
                print(f"Keine Berechtigung zum {action} in {guild.name}")
            except discord.HTTPException as e:
                print(f"Fehler beim {action} in {guild.name}: {e}")
            except Exception as e:
                print(f"Unbekannter Fehler beim {action} in {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Wird ausgelöst, wenn ein User gebannt wird."""
        # Erstelle ein pseudo-Member-Objekt für die Sync-Funktion
        # Da wir im Event nur 'user' (User Objekt) haben, nicht 'member' (Member Objekt mit Guild)
        # aber die Sync Funktion erwartet ein Member Objekt oder wir passen sie an.
        # Einfacher: Wir rufen die Logik direkt hier auf oder passen sync_to_other_servers an.
        
        main_guild_id = await self.config.main_guild_id()
        if guild.id != main_guild_id:
            return
            
        enabled = await self.config.enabled()
        if not enabled or not await self.config.sync_ban():
            return

        # Synchronisiere Ban
        await self.sync_ban_action(guild, user)

    async def sync_ban_action(self, guild: discord.Guild, user: discord.User, reason: Optional[str] = None):
        """Führt den Ban auf anderen Servern aus."""
        target_guilds = [g for g in self.bot.guilds if g.id != guild.id]
        
        for target_guild in target_guilds:
            try:
                # Prüfen ob User schon gebannt ist
                ban_entry = await target_guild.bans().find(user.id)
                if ban_entry:
                    continue
                
                await target_guild.ban(user, reason=f"Sync-Ban von {guild.name}: {reason}")
            except discord.Forbidden:
                pass
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Wird ausgelöst, wenn ein User entbannt wird."""
        main_guild_id = await self.config.main_guild_id()
        if guild.id != main_guild_id:
            return
            
        enabled = await self.config.enabled()
        if not enabled or not await self.config.sync_unban():
            return

        # Synchronisiere Unban
        await self.sync_unban_action(guild, user)

    async def sync_unban_action(self, guild: discord.Guild, user: discord.User):
        """Führt den Unban auf anderen Servern aus."""
        target_guilds = [g for g in self.bot.guilds if g.id != guild.id]
        
        for target_guild in target_guilds:
            try:
                await target_guild.unban(user, reason=f"Sync-Unban von {guild.name}")
            except discord.NotFound:
                pass # War nicht gebannt
            except discord.Forbidden:
                pass
            except Exception:
                pass

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
    await bot.add_cog(SBan(bot))
