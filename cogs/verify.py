import re
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

import discord
from discord import Member
from discord.asset import Asset
from discord.ext import commands
from discord.ext.commands import Bot

from cogs import errors
from repository import user_repo
from core.config import config
from core.emote import emote
from core import rubbercog, utils
from config.messages import Messages as messages


repository = user_repo.UserRepository()


class Verify(rubbercog.Rubbercog):
    def __init__(self, bot):
        super().__init__(bot)
        self.errors = errors.Errors(bot)
        self.rubbercog = rubbercog.Rubbercog(bot)
        # self.verification = verification.Verification(bot, repository)

    async def in_jail(ctx):
        """Return true if current channel is #jail"""
        if ctx.guild is None:
            # allow verification in DMs
            return True
        return ctx.channel.id == config.channel_jail

    async def send_mail(self, author, receiver_email, code):
        user_name = author.name
        bot_img = self.bot.user.avatar_url_as(static_format="png", size=128)
        user_img = author.avatar_url_as(static_format="png", size=32)
        h = utils.git_hash()[:7]
        cleartext = """\
            Tvůj verifikační kód pro VUT FEKT Discord server je: {code}.
            - Rubbergoddess (hash {h})
            """.format(
            code=code, h=h
        )
        richtext = """\
            <body style="background-color:#54355F;margin:0;text-align:center;">
            <div style="background-color:#54355F;margin:0;padding:20px;text-align:center;">
                <img src="{bot_img}" alt="Rubbergoddess" style="margin:0 auto;border-radius:100%;border:5px solid white;">
                <p style="display:block;color:white;font-family:Arial,Verdana,sans-serif;font-size:24px;">
                    <img src="{user_img}" alt="" style="height:20px;width:20px;top:4px;margin-right:6px;border-radius:100%;border:2px solid white;display:inline;position:relative;"><span>{user_name}</span>
                </p>
                <p style="display:block;color:white;font-family:Arial,Verdana,sans-serif;">Tvůj verifikační kód pro <span style="font-weight:bold;">VUT FEKT</span> Discord server:</p>
                <p style="color:#45355F;font-family:monospace;font-size:30px;letter-spacing:6px;font-weight:bold;background-color:white;display:inline-block;padding:16px 26px;margin:16px 0;border-radius:4px;">{code}</p>
                <p style="color:white;font-family:Arial,Verdana,sans-serif;margin:10px 0;">Můžeš ho použít jako <span style="font-weight:bold;color:#45355F;padding:5px 10px;font-family:monospace;background-color:white;border-radius:2px;">?submit {code}</span></p>
                <p style="display:block;color:white;font-family:Arial,Verdana,sans-serif;"><a style="color:white;text-decoration:none;font-weight:bold;" href="https://github.com/sinus-x/rubbergoddess" target="_blank">Rubbergoddess</a>, hash {h}</p>
            </div>
            </body>""".format(
            code=code, h=h, bot_img=bot_img, user_img=user_img, user_name=user_name
        )

        msg = MIMEMultipart("alternative")
        # FIXME Can this be abused?
        msg["Subject"] = "VUT FEKT verify → {}".format(user_name)
        msg["From"] = config.mail_address
        msg["To"] = receiver_email
        msg["Bcc"] = config.mail_address
        msg.attach(MIMEText(cleartext, "plain"))
        msg.attach(MIMEText(richtext, "html"))

        if config.debug:
            print(
                "Simulating verification mail: {} for {} ({})".format(
                    code, user_name, receiver_email
                )
            )
            return

        with smtplib.SMTP(config.mail_smtp_server, config.mail_smtp_port) as server:
            server.starttls()
            server.ehlo()
            server.login(config.mail_address, config.mail_password)
            server.send_message(msg)

    async def has_role(self, user, role_name):
        if type(user) == Member:
            return utils.has_role(user, role_name)
        else:
            guild = self.getGuild()
            member = await guild.fetch_member(user.id)
            return utils.has_role(member, role_name)

    async def gen_code_and_send_mail(self, message, email, group=None):
        # generate code
        code = "".join(random.choices(string.ascii_uppercase.replace("O", "") + string.digits, k=8))
        # send mail
        await self.send_mail(message.author, email, code)
        # save the newly generated code into the database
        repository.save_code(code=code, discord_id=message.author.id)
        # print approving answer
        domain = email.split("@")[1]
        c = "?verify "
        if group and group in ["FEKT", "VUT"]:
            c += group + "** [redacted]**"
        else:
            c += "**[redacted]**@" + domain
        identifier = "xlogin00" if email.endswith("vutbr.cz") else "e-mail"
        await message.channel.send(
            utils.fill_message(
                "verify_send_success", user=message.author.id, command=c, id=identifier
            ),
            delete_after=config.delay_verify,
        )

    async def login_check(self, string):
        # regex matches uppercase or lowercase VUT login, not if it contains "login"
        logex = re.compile(r"([x](?![l][o][g][i][n])[a-z]{5}\d[a-z0-9])")
        login = logex.match(string)
        if login is not None:
            login = login.group()
        else:
            login = " "
        return login

    async def code_check(self, string):
        # regex matches uppercase or lowercase VUT login, not if it contains "login"
        code_regex = re.compile(r"[A-Z0-9]{8}")
        code = code_regex.match(string)
        if code is not None:
            code = code.group().upper()
        else:
            code = " "
        return code

    @commands.cooldown(rate=5, per=30.0, type=commands.BucketType.user)
    @commands.check(in_jail)
    @commands.command()
    async def submit(self, ctx: commands.Context):
        """Verify user entry in database"""
        message = ctx.message

        # get variables
        args = tuple(re.split(r"\s+", str(message.content).strip("\r\n\t")))

        if len(args) != 2:
            await message.channel.send(
                utils.fill_message("verify_verify_format", user=message.author.id),
                delete_after=config.delay_verify,
            )
            try:
                await message.delete()
            except discord.HTTPException:
                return
            return

        # only process users that are not verified
        if not await self.has_role(message.author, config.role_verify):
            guild = self.getGuild()
            code = await self.code_check(args[1].upper())

            # test for common errors
            errmsg = None
            if args[1] == "kód" or args[1] == "kod":
                await message.channel.send(
                    utils.fill_message(
                        "verify_verify_no_code", user=message.author.id, emote=emote.facepalm
                    ),
                    delete_after=config.delay_verify,
                )
                try:
                    await message.delete()
                except discord.HTTPException:
                    return
                return

            elif code is None:
                await message.channel.send(
                    utils.fill_message(
                        "verify_verify_bad_input", user=message.author.id, emote=emote.facepalm
                    ),
                    delete_after=config.delay_verify,
                )
                try:
                    await message.delete()
                except discord.HTTPException:
                    return
                return

            try:
                new_user = repository.filterId(discord_id=message.author.id)[0]
            except IndexError:
                new_user = None

            errmsg = None
            if new_user is None:
                await message.channel.send(
                    utils.fill_message("verify_verify_not_found", user=message.author.id),
                    delete_after=config.delay_verify,
                )
            else:
                # check the verification code
                if code.replace("O", "0") != new_user.code:
                    await message.channel.send(
                        utils.fill_message("verify_verify_wrong_code", user=message.author.id),
                        delete_after=config.delay_verify,
                    )
                    errmsg = "Neúspěšný pokus o verifikaci kódem"
                else:
                    group = new_user.group

                    if group is None:
                        await message.channel.send(
                            utils.fill_message(
                                "verify_verify_manual",
                                user=message.author.id,
                                admin=config.admin_id,
                            )
                        )
                        errmsg = "Neúspěšný pokus o verifikaci kódem (chybí skupina)"
                    else:
                        # add verify role
                        guild = self.getGuild()
                        verify = guild.get_role(config.role_verify)
                        role = discord.utils.get(guild.roles, name=group)
                        if isinstance(ctx.channel, discord.channel.DMChannel):
                            member = guild.get_member(message.author.id)
                            await message.channel.send(
                                utils.fill_message(
                                    "verify_verify_success_public",
                                    user=message.author.id,
                                    group=group,
                                )
                            )
                        else:
                            member = message.author
                            await message.channel.send(
                                utils.fill_message(
                                    "verify_verify_success_public",
                                    user=message.author.id,
                                    group=group,
                                ),
                                delete_after=config.delay_verify,
                            )

                        await member.add_roles(verify)
                        await member.add_roles(role)

                        # save to database
                        repository.save_verified(discord_id=message.author.id)

                        # text user
                        await member.send(
                            utils.fill_message(
                                "verify_verify_success_private", user=message.author.id
                            )
                        )
                        if role.name == "FEKT":
                            await member.send(messages.verify_congrats_fekt)
                        elif role.name == "TEACHER":
                            await member.send(messages.verify_congrats_teacher)

                            embed = discord.Embed(
                                title="New teacher verification", color=config.color
                            )
                            embed.add_field(name="User", value=member.mention)
                            channel = self.bot.get_channel(config.channel_guildlog)
                            await channel.send(embed=embed)
                        else:
                            await member.send(messages.verify_congrats_guest)
            if errmsg:
                embed = discord.Embed(title=errmsg, color=config.color)
                embed.add_field(
                    name="User",
                    value=f"**{discord.utils.escape_markdown(message.author.name)}** ({message.author.id})\n{message.author.mention}",
                )
                embed.add_field(name="Command", value=message.content, inline=False)
                channel = self.bot.get_channel(config.channel_botlog)
                await channel.send(embed=embed)
        try:
            await message.delete()
        except discord.HTTPException:
            return

    @commands.cooldown(rate=5, per=30.0, type=commands.BucketType.user)
    @commands.check(in_jail)
    @commands.command(aliases=["getcode"])
    async def verify(self, ctx: commands.Context):
        # get variables
        message = ctx.message
        args = tuple(re.split(r"\s+", str(message.content).strip("\r\n\t")))
        login = None
        group = None
        if len(args) == 2 and "@" in args[1]:
            login = args[1].lower()
            if args[1].endswith("stud.feec.vutbr.cz"):
                group = "FEKT"
                login = await self.login_check(login)
            elif args[1].endswith("@feec.vutbr.cz"):
                group = "FEKT"
                login = await self.login_check(login)
            elif args[1].endswith("vutbr.cz"):
                group = "VUT"
                login = await self.login_check(login)
        elif len(args) == 3:
            group = args[1].upper()
            if group == "TEACHER":
                if (
                    args[2].lower().endswith("@vutbr.cz")
                    or args[2].lower().endswith("@feec.vutbr.cz")
                    or args[2].lower().endswith("@stud.feec.vutbr.cz")
                ):
                    login = args[2].lower()
                else:
                    login = " "
            else:
                login = await self.login_check(args[2].lower())
        else:
            await message.channel.send(
                messages.verify_send_format, delete_after=config.delay_verify
            )
            try:
                await message.delete()
            except discord.HTTPException:
                return
            return

        # check if the user doesn't have the verify role
        if await self.has_role(message.author, config.role_verify):
            # TODO Log as verify_log(channel,user,message)
            await message.channel.send(
                utils.fill_message(
                    "verify_already_verified_role", user=message.author.id, admin=config.admin_id
                )
            )
        else:

            jail_info = self.rubbercog.getGuild().get_channel(config.channel_jailinfo)
            errmsg = None

            if login == "e-mail" or login == " ":
                await message.channel.send(
                    utils.fill_message(
                        "verify_wrong_arguments",
                        user=message.author.id,
                        login=login,
                        emote=emote.facepalm,
                        channel=jail_info.mention,
                    ),
                    delete_after=config.delay_verify,
                )
                try:
                    await message.delete()
                except discord.HTTPException:
                    # TODO log
                    return
                return
            # unknown - pending - verified - kicked - banned
            errmsg = None
            try:
                u = repository.filterId(discord_id=message.author.id)[0]
            except IndexError:
                u = None
            try:
                l = repository.filterLogin(login=login)[0]
            except IndexError:
                l = None

            if u is None or u and u.status == "unknown":
                if l is None:
                    # send verify message
                    if group and group.upper() == "FEKT":
                        email = "{}@stud.feec.vutbr.cz".format(login)
                    elif group and group.upper() == "VUT":
                        email = "{}@vutbr.cz".format(login)
                    else:
                        if "@" not in login:
                            await message.channel.send(
                                utils.fill_message(
                                    "verify_wrong_arguments",
                                    user=message.author.id,
                                    emote=emote.facepalm,
                                    channel=jail_info.mention,
                                    login="**[redacted]]**",
                                )
                            )
                            return
                        elif group and group.upper() == "TEACHER":
                            email = login
                        elif login.endswith("muni.cz"):
                            email = login
                            group = "MUNI"
                        elif login.endswith("cuni.cz"):
                            email = login
                            group = "CUNI"
                        elif login.endswith("cvut.cz"):
                            email = login
                            group = "ČVUT"
                        elif login.endswith("vsb.cz"):
                            email = login
                            group = "VŠB"
                        elif login.endswith("zcu.cz"):
                            email = login
                            group = "ZČU"
                        else:
                            email = login
                            group = "GUEST"
                    repository.add_user(
                        discord_id=message.author.id,
                        login=login,
                        group=group.upper(),
                        status="pending",
                    )
                    await self.gen_code_and_send_mail(message, email, group=group)
                else:
                    errmsg = "Login už v db existuje!"
                    await message.channel.send(
                        utils.fill_message(
                            "verify_login_exists", user=message.author.id, admin=config.admin_id
                        )
                    )

            elif u.status == "pending":
                # say that message has been sent
                await message.channel.send(
                    utils.fill_message(
                        "verify_already_sent", user=message.author.id, admin=config.admin_id
                    ),
                    delete_after=config.delay_verify,
                )

            elif u.status == "verified":
                # say that the user is already verified
                # TODO do nothing if not in #jail
                await message.channel.send(
                    utils.fill_message(
                        "verify_already_verified_db", user=message.author.id, admin=config.admin_id
                    )
                )

            elif u.status == "kicked":
                # say that the user has been kicked before
                errmsg = "Pokus o verify s **kicked** záznamem!"
                await message.channel.send(
                    utils.fill_message(
                        "verify_send_kicked", user=message.author.id, admin=config.admin_id
                    )
                )

            elif u.status == "banned":
                # say that the user has been banned before
                errmsg = "Pokus o verify s **banned** záznamem!"
                await message.channel.send(
                    utils.fill_message(
                        "verify_send_banned", user=message.author.id, admin=config.admin_id
                    )
                )

            else:
                # show help
                await message.channel.send(
                    utils.fill_message("verify_send_format", user=message.author.id),
                    delete_after=config.delay_verify,
                )

            if errmsg:
                embed = discord.Embed(title=errmsg, color=config.color)
                embed.add_field(
                    name="User",
                    value=f"**{discord.utils.escape_markdown(message.author.name)}** ({message.author.id})\n{message.author.mention}",
                )
                embed.add_field(name="Command", value=message.content, inline=False)
                channel = self.bot.get_channel(config.channel_botlog)
                await channel.send(embed=embed)

        try:
            await message.delete()
        except discord.HTTPException:
            return

    @submit.error
    @verify.error
    async def verifyError(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await self.throwNotification(ctx, messages.verify_not_jail)
            return


def setup(bot):
    bot.add_cog(Verify(bot))
