# MIT License
#
# Copyright (c) 2023 jvherck (on GitHub)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import discord, os, random, json
from discord.ext.commands import Bot, Context, max_concurrency, BucketType, cooldown, MemberConverter
from discord.ext.commands.errors import CommandOnCooldown
from dotenv import load_dotenv
from time import sleep, time
from roastedbyai import Conversation, MessageLimitExceeded, CharacterLimitExceeded

load_dotenv()

# Using the bot's ID in a mention as prefix
bot = Bot(command_prefix="<@857170119108722708> ",
          intents=discord.Intents.all())
mc = MemberConverter()

# Storing all the roasts in a variable
with open("database/roast.json", "r", encoding="UTF-8") as f:
    roasts = json.load(f)
f.close()


@bot.event
async def on_ready():
    print("Bot logged in as {}".format(bot.user))


@bot.command(name="roast")
@max_concurrency(1, BucketType.user)
@max_concurrency(4, BucketType.channel)
@cooldown(1, 15, BucketType.user)
async def _roast(ctx: Context, target: str = None):
    """
    Start an AI roast session. Take turns in roasting the AI and the AI roasting you.
    If you want to stop, simply say "stop" or "quit".

    Subcommands:
    > - `me`: start a roast battle with the AI
    > - `@mention` | `<username>`: roast someone else

    Cooldown:
    > Once every minute per user

    Concurrency:
    > Maximum of 1 session per user at the same time
    > Maximum of 4 sessions per channel at the same time
    """
    if target != "me":
        try:
            target = await mc.convert(ctx, target)
        except:
            target = None
        await _roast_someone(ctx, target)
        return
    pb = PromptButtons()
    msg = await ctx.reply(
        "We'll be taking turns in trying to roast each other. Are you sure you can handle this and want to continue?",
        view=pb)
    pb.msg = msg
    pb.ctx = ctx


class PromptButtons(discord.ui.View):

    def __init__(self, *, timeout=180):
        self.msg: discord.Message = None
        self.ctx: Context = None
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "This is not your roast battle.", ephemeral=True)
            return
        await self.msg.edit(
            content=
            "You accepted the roast battle. May the biggest chicken be the hottest roast.",
            view=None)
        msg = await self.ctx.send(
            f"{self.ctx.author.mention} Alright, give me your best roast and we'll take turns.\nIf you want to stop, simply click the button or send \"stop\" or \"quit\"."
        )
        await _roast_battle(self.ctx, prev_msg=msg)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "This is not your roast battle.", ephemeral=True)
            return
        await self.msg.edit(
            content="You cancelled and chickened out of the roast battle.",
            view=None)


class RoastBattleCancel(discord.ui.View):

    def __init__(self, *, timeout=180):
        self.ctx: Context = None
        self.convo: Conversation = None
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.grey)
    async def stop_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "This is not your roast battle.", ephemeral=True)
            return
        self.convo.kill()
        self.convo.killed = True
        await interaction.message.edit(content=interaction.message.content,
                                       view=None)
        await interaction.response.send_message("Boo, you're no fun.")
        return


async def _roast_battle(ctx: Context, prev_msg: discord.Message):
    convo = Conversation()

    def check(m: discord.Message):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

    while convo.alive is True:
        try:
            msg: discord.Message = await bot.wait_for("message",
                                                      check=check,
                                                      timeout=300)
            response = None
            while response is None:
                try:
                    if hasattr(convo, "killed"):
                        # on line 120 we set convo.killed to True, this attribute is not a standard attribute of the
                        # Conversation class, so here we check if that attribute exists, and if it does, we have to
                        # stop the command from running as the user clicked the stop button
                        return
                    await ctx.typing()
                    if msg.content.lower() in ["stop", "quit"]:
                        await ctx.channel.send(
                            f"{ctx.author.mention} you're so lame bro, chickening out like this. "
                            f"But I wouldn't want to hurt your few little braincells much more, buh-bye."
                        )
                        convo.kill()
                        return
                    else:
                        response = convo.send(msg.content)
                except TimeoutError:
                    sleep(1)
                    await ctx.send(
                        f"{ctx.author.mention} I'm too tired to continue talking right now, buh-bye."
                    )
                    convo.kill()
                    return
                except MessageLimitExceeded:
                    await ctx.reply(
                        "It's been enough roasting now, I can already smell you're starting to burn..."
                    )
                    return
                except CharacterLimitExceeded:
                    await ctx.reply(
                        "Too much to read. Send 250 characters maximum, no need to write a whole book about me!\nCome on, try again!"
                    )
                    break
                else:
                    await prev_msg.edit(content=prev_msg.content, view=None)
                    rbc = RoastBattleCancel()
                    prev_msg = await msg.reply(response, view=rbc)
                    rbc.ctx = ctx
                    rbc.convo = convo
        except TimeoutError:
            convo.kill()
    if convo.alive:
        convo.kill()


async def _roast_someone(ctx: Context, target: discord.Member | None = None):
    """Roast someone :smiling_imp:"""
    if target is None:
        dumb = [
            "https://media.tenor.com/CZoZV7amWI8AAAAC/roast-turkey-turkey.gif",
            "https://media.giphy.com/media/f6a97XAWuW5AA1cViz/giphy.gif",
            "https://media.giphy.com/media/ZvwTFklWHDTozWT5CW/giphy.gif",
            "https://media.giphy.com/media/JThXXdHrFAQ0LNsVka/giphy.gif",
            "https://media.tenor.com/XcUy7gyqpWgAAAAd/turkey-roast.gif",
            "https://media.tenor.com/X1bcAP-Vy_sAAAAC/roast-in-flame-boy.gif",
            "https://media.tenor.com/pp_7aPIRIwkAAAAC/hog-hog-roast.gif",
            "You're so stupid you even forgot to mention someone to roast, dumbass.",
            "Cooking up the perfect roast... Roast ready at <t:{}:f>".format(
                int(time() + random.randint(50_000, 500_000_000))),
            "Who do you want to roast, dumbass. Next time tell me who to roast."
        ]
        await ctx.reply(random.choice(dumb))
        return
    elif target.id == ctx.author.id:
        dumb = [
            "Look in the mirror, there's my roast. Now next time give me someone else to roast",
            "Why do you even wanna roast yourself?",
            "https://tenor.com/view/roast-turkey-turkey-thanksgiving-gif-18067752",
            "You get no bitches, so lonely you're even trying to roast yourself...",
            "Stop roasting yourself, there's so many roasts ready to use on others",
            "Cooking up the perfect roast... Roast ready at <t:{}:f>".format(
                int(time() + random.randint(50_000, 500_000_000))),
            "Don't tell me there's {} other people to roast, and out of all those people you want to roast yourself??"
            .format(ctx.guild.member_count - 1),
            "Are you okay? Do you need mental help? Why is your dumbass trying to roast itself..."
        ]
        await ctx.reply(random.choice(dumb))
        return
    elif target.id == bot.user.id:
        dumb = [
            "You really think I'm gonna roast myself? :joy:",
            "You're just dumb as hell for thinking I would roast myself...",
            "Lol no", "Sike you thought. I'm not gonna roast myself, dumbass.",
            "I'm not gonna roast myself, so instead I'll roast you.\n",
            "Buddy, do you really think you're so funny? I might just be a Discord bot, but I'm not gonna roast myself :joy::skull:",
            "I'm just perfect, there's nothing to roast about me :angel:"
        ]
        await ctx.reply(random.choice(dumb))
    initroast = random.choice(roasts)
    roast_expl = None
    if type(initroast) is list:
        _roast = initroast[0].replace("{mention}",
                                      f"**{target.display_name}**").replace(
                                          "{author}",
                                          f"**{ctx.author.display_name}**")
        roast_expl = initroast[1].replace(
            "{mention}", f"**{target.display_name}**").replace(
                "{author}", f"**{ctx.author.display_name}**")
    else:
        _roast = initroast
    roast = f"{target.mention} " + _roast

    def check(msg):
        return msg.channel.id == ctx.channel.id and msg.content.lower(
        ).startswith(("what", "what?", "i dont get it", "i don't get it"))

    await ctx.channel.send(roast)
    if roast_expl:
        try:
            msg: discord.Message = await bot.wait_for("message",
                                                      check=check,
                                                      timeout=15)
            await ctx.typing()
            sleep(1.5)
            await msg.reply(roast_expl)
        except Exception as e:
            raise e


@bot.event
async def on_command_error(ctx, ex):
    if isinstance(ex, CommandOnCooldown):
        await ctx.reply(
            f"You're on cooldown, try again in **`{round(ex.retry_after, 1)}s`**"
        )


if __name__ == "__main__":
    bot.run(os.environ.get("TOKEN"), reconnect=True)
