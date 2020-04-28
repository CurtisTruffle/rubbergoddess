import re
import datetime

import discord
from discord.ext import commands

from core.config import config
from core.emote import emote
from core import check, rubbercog, utils
from config.messages import Messages as messages
from logic.convert import Convert as convert

class FitWide(rubbercog.Rubbercog):
    def __init__(self, bot):
        super().__init__(bot)
        self.visible = False

    async def is_in_modroom(ctx):
        return ctx.message.channel.id == config.channel_mods

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_in_modroom)	
    @commands.has_permissions(administrator=True)	
    @commands.command()	
    async def hoarders(self, ctx: commands.Context):
        message = tuple(re.split(r'\s+', str(ctx.message.content).strip("\r\n\t")))
        guild = self.bot.get_guild(config.guild_id)
        members = guild.members

        hoarders = []
        for member in members:	
            prog_count = 0	
            for role in member.roles:	
                if role < discord.utils.get(guild.roles, name='---FEKT') and role > discord.utils.get(guild.roles, name='---'):	
                    prog_count += 1	
            if prog_count > 1:	
                hoarders.append((member, prog_count))

        msg = ""	

        if len(hoarders) == 0:	
            msg = messages.hoarders_none	
        else:	
            for member, role_count in hoarders:	
                line = "{id} - {name} (Počet ročníků: {num})\n".format(id=member.id, name=member.name, num=role_count)
                if len(message) == 2 and message[1] == "warn":
                    await member.send(utils.fill_message(
                            "hoarders_warn", user=member.id))
                if len(line) + len(msg) >= 2000:	
                    await ctx.send(msg)	
                    msg = line	
                else:	
                    msg += line	

        await ctx.send(msg)

    #TODO Adapt to FEKT roles
    @commands.check(check.is_mod)
    @commands.check(check.is_in_modroom)
    @commands.command()
    async def offer_subjects(self, ctx, group = None):
        add_subjects = discord.utils.get(self.getGuild().channels, name="add-subjects")

        # when adding everything, delete all previous posts
        deleted = 0
        if not group:
            deleted = len(await add_subjects.purge())

        ctr_ca = 0
        ctr_ch = 0
        for category in self.getGuild().categories:
            has_subjects = False
            if not group:
                for c in category.text_channels:
                    if c.name in config.subjects:
                        has_subjects = True
                        break
            if not group and not has_subjects:
                continue

            elif group and category.name.lower() != group.lower():
                continue

            await add_subjects.send("**{}**".format(category.name.upper()))

            ctr_ca += 1
            msg = ""
            i = 0
            for channel in category.text_channels:
                if channel.name not in config.subjects:
                    continue
                if i >= 10:
                    await add_subjects.send(msg)
                    i = 0
                    msg = ""
                msg += "\n{} #{}".format(convert.emote_number_from_int(i), channel.name)
                msg += " **{}**".format(channel.topic) if channel.topic else ""
                i += 1
                ctr_ch += 1
            await add_subjects.send(msg)

        title = config.prefix + "offer_subjects result"
        cleared = "Yes, {} post{}".format(deleted, "s" if deleted > 1 else "") if group is None else "No"
        embed = discord.Embed(title=title, color=config.color)
        embed.add_field(name="Cleared?", value=cleared, inline=False)
        embed.add_field(name="Groups", value=ctr_ca, inline=True)
        embed.add_field(name="Subjects", value=ctr_ch, inline=True)
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

        return

    #TODO Rewrite
    @commands.check(check.is_elevated)
    @commands.command()
    async def purge(self, ctx, channel, limit = None, pinMode = "pinSkip"):
        #TODO Add user argument
        if channel == ".":
            ch = ctx.channel
            channel = ch.name
        else:            
            ch = discord.utils.get(self.getGuild().text_channels, name=channel.replace("#", ""))

        if limit:
            try:
                limit = int(limit) + 1
            except ValueError:
                self.purgeHelp()

        if limit:
            msgs = ch.history(limit=limit)
        else:
            msgs = ch.history()
        ctr_del = 0
        ctr_skip = 0
        ctr_pin = 0
        ctr_err = 0
        async for m in msgs:
            if m.pinned and pinMode == "pinStop":
                break
            elif m.pinned and pinMode == "pinSkip":
                ctr_skip += 1
                continue
            elif m.pinned and pinMode == "pinIgnore":
                ctr_pin += 1
            try:
                await m.delete()
                ctr_del += 1
            except discord.HTTPException:
                ctr_err += 1

        embed = discord.Embed(title="?purge", color=config.color)
        embed.add_field(name="Settings", value="Channel **{}**, limit **{}**, pinMode **{}**".
            format(channel, limit-1 if limit else "none", pinMode if pinMode else "ignore"))
        embed.add_field(name="Result",
            value="**{deleted}** removed (**{pinned}** were pinned), **{skipped}** skipped.\n" \
                "**{err}** errors occured.".format(
                deleted=ctr_del-1 + ctr_pin, skipped=ctr_skip, pinned=ctr_pin, err=ctr_err))
        embed.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)
        channel = self.getGuild().get_channel(config.channel_botlog)
        await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(FitWide(bot))
