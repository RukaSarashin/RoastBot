# MIT License

# Copyright (c) 2023 jvherck (on GitHub)

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
bot = Bot(command_prefix="<@1140242477270454363> ",
          intents=discord.Intents.all())
mc = MemberConverter()

# Storing all the roasts in a variable
with open("database/roast.json", "r", encoding="UTF-8") as f:
    roasts = json.load(f)
f.close()


@bot.event
async def on_ready():
    print("Bot logged in as {}".format(bot.user))


@bot.command(name="ativar")
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
        "Estaremos nos revezando tentando assar um ao outro. Tem certeza de que pode lidar com isso e deseja continuar?",
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
                "Esta não é a sua batalha assado.", ephemeral=True)
            return
        await self.msg.edit(
            content=
            "Você aceitou a batalha do assado. Que o maior frango seja o assado mais gostoso.",
            view=None)
        msg = await self.ctx.send(
            f"{self.ctx.author.mention} Tudo bem, me dê seu melhor assado e nós revezaremos.\nSe quiser parar, basta clicar no botão ou enviar \"parar\" ou \"sair\"."
        )
        await _roast_battle(self.ctx, prev_msg=msg)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Esta não é a sua batalha assado.", ephemeral=True)
            return
        await self.msg.edit(
            content="Você cancelou e se acovardou na batalha do assado.",
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
                "Esta não é a sua batalha assado.", ephemeral=True)
            return
        self.convo.kill()
        self.convo.killed = True
        await interaction.message.edit(content=interaction.message.content,
                                       view=None)
        await interaction.response.send_message("Boo, você não é divertido.")
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
                            f"{ctx.author.mention} você é tão manco mano, se acovardando assim. "
                            f"Mas eu não gostaria de machucar muito mais suas poucas células cerebrais, tchau."
                        )
                        convo.kill()
                        return
                    else:
                        response = convo.send(msg.content)
                except TimeoutError:
                    sleep(1)
                    await ctx.send(
                        f"{ctx.author.mention} Estou muito cansado para continuar falando agora, tchau."
                    )
                    convo.kill()
                    return
                except MessageLimitExceeded:
                    await ctx.reply(
                        "Já está assando o suficiente agora, eu já posso sentir o cheiro que você está começando a queimar..."
                    )
                    return
                except CharacterLimitExceeded:
                    await ctx.reply(
                        "Muito para ler. Envie no máximo 250 caracteres, não há necessidade de escrever um livro inteiro sobre mim!\nVenha, tente novamente!"
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
    """assar alguém :smiling_imp:"""
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
            "Quem você quer assar, idiota. Da próxima vez, diga-me quem assar."
        ]
        await ctx.reply(random.choice(dumb))
        return
    elif target.id == ctx.author.id:
        dumb = [
            "Olhe no espelho, lá está o meu assado. Agora, da próxima vez, me dê outra pessoa para assar",
            "Por que você ainda quer se assar?",
            "https://tenor.com/view/roast-turkey-turkey-thanksgiving-gif-18067752",
            "Você não tem cadelas, tão sozinho que está tentando se assar...",
            "Pare de se assar, há tantos assados prontos para usar nos outros",
            "Preparando o assado perfeito... Assado pronto em <t:{}:f>".format(
                int(time() + random.randint(50_000, 500_000_000))),
            "Não me diga que há {} outras pessoas para assar, e de todas essas pessoas você quer assar você mesmo??"
            .format(ctx.guild.member_count - 1),
            "Você está bem? Você precisa de ajuda mental? Por que seu idiota está tentando se assar..."
        ]
        await ctx.reply(random.choice(dumb))
        return
    elif target.id == bot.user.id:
        dumb = [
            "Acha mesmo que vou me assar? :joy:",
            "Você é burro pra caramba por pensar que eu iria me assar...",
            "Lol não", "Sike você pensou. Eu não vou me assar, idiota.",
            "Eu não vou me assar, então vou assar você.\n",
            "Amigo, você realmente se acha tão engraçado? Posso ser apenas um bot do Discord, mas não vou me assar :joy::skull:",
            "Eu sou simplesmente perfeito, não há nada para assar sobre mim :angel:"
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
            f"Você está em cooldown, tente novamente em **`{round(ex.retry_after, 1)}s`**"
        )


if __name__ == "__main__":
    bot.run(os.environ.get("TOKEN"), reconnect=True)
