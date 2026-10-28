import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import datetime
import aiosqlite
import os

ROLES_POR_NIVEL = {
    5: "Nivel 5",
    10: "Nivel 10",
    15: "Nivel 15",
    20: "Nivel 20",
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def iniciar_db():
    db = await aiosqlite.connect("datos.db")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS niveles (
            usuario_id TEXT PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            nivel INTEGER DEFAULT 1
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS economia (
            usuario_id TEXT PRIMARY KEY,
            monedas INTEGER DEFAULT 100
        )
    """)
    await db.commit()
    await db.close()

@bot.event
async def on_ready():
    print(f"¡El bot {bot.user} está en línea!")
    await iniciar_db()
    print("Base de datos lista ✅")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="!ayuda • SupportPro"
    ))
    try:
        synced = await bot.tree.sync()
        print(f"Comandos slash sincronizados: {len(synced)}")
    except Exception as e:
        print(f"No se pudieron sincronizar los slash: {e}")

@bot.event
async def on_member_join(miembro):
    canal = discord.utils.get(miembro.guild.text_channels, name="general")
    if canal:
        embed = discord.Embed(
            title=f"👋 ¡Bienvenido {miembro.display_name}!",
            description=f"¡Hola {miembro.mention}! Bienvenido a **{miembro.guild.name}**. Escribe `!ayuda` para ver todos los comandos.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=miembro.avatar.url)
        await canal.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    db = await aiosqlite.connect("datos.db")
    usuario_id = str(message.author.id)

    await db.execute("""
        INSERT INTO niveles (usuario_id, xp, nivel) VALUES (?, 1, 1)
        ON CONFLICT(usuario_id) DO UPDATE SET xp = xp + 1
    """, (usuario_id,))
    await db.commit()

    cursor = await db.execute("SELECT xp, nivel FROM niveles WHERE usuario_id = ?", (usuario_id,))
    fila = await cursor.fetchone()
    await cursor.close()
    await db.close()

    if fila:
        xp, nivel = fila
        nuevo_nivel = xp // 20 + 1
        if nuevo_nivel > nivel:
            db = await aiosqlite.connect("datos.db")
            await db.execute("UPDATE niveles SET nivel = ? WHERE usuario_id = ?", (nuevo_nivel, usuario_id))
            await db.commit()
            await db.close()
            await message.channel.send(f"🎉 ¡{message.author.mention} subió al nivel **{nuevo_nivel}**!")

            if nuevo_nivel in ROLES_POR_NIVEL:
                rol = discord.utils.get(message.guild.roles, name=ROLES_POR_NIVEL[nuevo_nivel])
                if rol:
                    try:
                        await message.author.add_roles(rol)
                        await message.channel.send(f"🏅 ¡{message.author.mention} recibió el rol **{rol.name}**!")
                    except Exception:
                        await message.channel.send("⚠️ No pude asignar el rol. Revisa que el bot tenga permisos de 'Gestionar roles'.")

    await bot.process_commands(message)

@bot.command()
async def nivel(ctx, miembro: discord.Member = None):
    if miembro is None:
        miembro = ctx.author
    db = await aiosqlite.connect("datos.db")
    cursor = await db.execute("SELECT xp, nivel FROM niveles WHERE usuario_id = ?", (str(miembro.id),))
    fila = await cursor.fetchone()
    await cursor.close()
    await db.close()

    if fila:
        xp, nivel = fila
        xp_siguiente = nivel * 20
        embed = discord.Embed(
            title=f"📊 Nivel de {miembro.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Nivel", value=f"**{nivel}**", inline=True)
        embed.add_field(name="XP", value=f"{xp} / {xp_siguiente}", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"{miembro.mention} todavía no tiene XP. ¡Escribe mensajes para ganar!")

@bot.command()
async def monedas(ctx, miembro: discord.Member = None):
    if miembro is None:
        miembro = ctx.author
    db = await aiosqlite.connect("datos.db")
    cursor = await db.execute("SELECT monedas FROM economia WHERE usuario_id = ?", (str(miembro.id),))
    fila = await cursor.fetchone()
    await cursor.close()
    await db.close()

    if fila:
        await ctx.send(f"💰 {miembro.display_name} tiene **{fila[0]}** monedas.")
    else:
        await ctx.send(f"💰 {miembro.display_name} tiene **100** monedas.")

@bot.command()
async def diario(ctx):
    db = await aiosqlite.connect("datos.db")
    usuario_id = str(ctx.author.id)
    await db.execute("""
        INSERT INTO economia (usuario_id, monedas) VALUES (?, 150)
        ON CONFLICT(usuario_id) DO UPDATE SET monedas = monedas + 150
    """, (usuario_id,))
    await db.commit()
    await db.close()
    await ctx.send(f"✅ {ctx.author.mention} reclamó su recompensa diaria: **+150 monedas** 💰")

@bot.command()
async def apostar(ctx, cantidad: int):
    if cantidad <= 0:
        await ctx.send("❌ Pon una cantidad válida.")
        return

    db = await aiosqlite.connect("datos.db")
    usuario_id = str(ctx.author.id)
    cursor = await db.execute("SELECT monedas FROM economia WHERE usuario_id = ?", (usuario_id,))
    fila = await cursor.fetchone()
    await cursor.close()

    monedas_actuales = fila[0] if fila else 100
    if cantidad > monedas_actuales:
        await db.close()
        await ctx.send(f"❌ No tienes suficientes monedas. Tienes **{monedas_actuales}**.")
        return

    if random.random() < 0.5:
        await db.execute("UPDATE economia SET monedas = monedas + ? WHERE usuario_id = ?", (cantidad, usuario_id))
        await db.commit()
        await db.close()
        await ctx.send(f"🎲 ¡Ganaste **{cantidad}** monedas! Ahora tienes **{monedas_actuales + cantidad}** 💰")
    else:
        await db.execute("UPDATE economia SET monedas = monedas - ? WHERE usuario_id = ?", (cantidad, usuario_id))
        await db.commit()
        await db.close()
        await ctx.send(f"😢 Perdiste **{cantidad}** monedas. Ahora tienes **{monedas_actuales - cantidad}** 💰")

@bot.command()
async def ayuda(ctx):
    embed = discord.Embed(
        title="🤖 SupportPro — Ayuda",
        description="Bot de soporte, moderación y economía premium.",
        color=discord.Color.blue()
    )
    embed.add_field(name="⚡ Utilidades", value="`!ping` · `!info` · `!avatar` · `!userinfo`", inline=False)
    embed.add_field(name="🛡️ Moderación", value="`!clear` · `!kick` · `!ban`", inline=False)
    embed.add_field(name="📊 Niveles", value="`!nivel` — gana XP al escribir", inline=False)
    embed.add_field(name="💰 Economía", value="`!monedas` · `!diario` · `!apostar`", inline=False)
    embed.add_field(name="🎮 Entretenimiento", value="`!dado` · `!bola8` · `!coin`", inline=False)
    embed.add_field(name="🎫 Tickets", value="Usa el botón de abajo o escribe `!ticket`", inline=False)
    embed.set_footer(text="SupportPro • Hecho con 💙 por DOKI")
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! 🏓 {round(bot.latency * 1000)}ms")

@bot.command()
async def info(ctx):
    embed = discord.Embed(
        title="🤖 SupportPro",
        description="Bot de soporte, moderación y economía para tu servidor.",
        color=discord.Color.blue()
    )
    embed.add_field(name="📊 Servidores", value=f"{len(bot.guilds)}", inline=True)
    embed.add_field(name="👥 Usuarios", value=f"{len(bot.users)}", inline=True)
    embed.add_field(name="⚡ Latencia", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="📅 Creado", value="por DOKI", inline=True)
    embed.set_footer(text="SupportPro • Bot en desarrollo")
    await ctx.send(embed=embed)

@bot.command()
async def avatar(ctx, miembro: discord.Member = None):
    if miembro is None:
        miembro = ctx.author
    embed = discord.Embed(title=f"Avatar de {miembro.display_name}", color=discord.Color.blue())
    embed.set_image(url=miembro.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, miembro: discord.Member = None):
    if miembro is None:
        miembro = ctx.author
    embed = discord.Embed(title=f"Información de {miembro.display_name}", color=discord.Color.green())
    embed.add_field(name="🆔 ID", value=miembro.id, inline=True)
    embed.add_field(name="📅 Se unió", value=miembro.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📅 Cuenta creada", value=miembro.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.set_thumbnail(url=miembro.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, cantidad: int = 5):
    if cantidad > 100:
        await ctx.send("❌ Máximo 100 mensajes.")
        return
    await ctx.channel.purge(limit=cantidad + 1)
    await ctx.send(f"🧹 Borré {cantidad} mensajes.", delete_after=3)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, miembro: discord.Member, *, razon="Sin razón"):
    await miembro.kick(reason=razon)
    await ctx.send(f"👢 {miembro.mention} fue expulsado. Razón: {razon}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, miembro: discord.Member, *, razon="Sin razón"):
    await miembro.ban(reason=razon)
    await ctx.send(f"🔨 {miembro.mention} fue baneado. Razón: {razon}")

@bot.command()
async def dado(ctx):
    await ctx.send(f"🎲 Tiraste el dado y salió: **{random.randint(1, 6)}**")

@bot.command()
async def bola8(ctx, *, pregunta):
    respuestas = [
        "Sí, definitivamente.",
        "Sin duda.",
        "Puede ser.",
        "Mejor no te digo ahora.",
        "No cuentes con eso.",
        "Muy probable.",
        "Las señales dicen que sí.",
        "Pregunta otra vez más tarde.",
    ]
    await ctx.send(f"🎱 {ctx.author.mention}: {random.choice(respuestas)}")

@bot.command()
async def coin(ctx):
    resultado = random.choice(["Cara", "Cruz"])
    await ctx.send(f"🪙 Tiré la moneda y salió: **{resultado}**")

class TicketButton(Button):
    def __init__(self):
        super().__init__(label="🎫 Abrir ticket", style=discord.ButtonStyle.green)

    async def callback(self, interaction):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites
        )
        embed = discord.Embed(
            title="🎫 Ticket abierto",
            description=f"¡Hola {interaction.user.mention}! Cuéntanos en qué podemos ayudarte.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Tu ticket se abrió en {channel.mention}", ephemeral=True
        )

@bot.command()
async def ticket(ctx):
    view = View()
    view.add_item(TicketButton())
    embed = discord.Embed(
        title="🎫 Soporte",
        description="¿Necesitas ayuda? Pulsa el botón para abrir un ticket privado.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)

@bot.tree.command(name="ping", description="Mide la latencia del bot")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! 🏓 {round(bot.latency * 1000)}ms")

@bot.tree.command(name="info", description="Información del bot")
async def slash_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 SupportPro",
        description="Bot de soporte, moderación y economía.",
        color=discord.Color.blue()
    )
    embed.add_field(name="⚡ Latencia", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ticket", description="Abre un ticket de soporte")
async def slash_ticket(interaction: discord.Interaction):
    view = View()
    view.add_item(TicketButton())
    embed = discord.Embed(
        title="🎫 Soporte",
        description="Pulsa el botón para abrir un ticket privado.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=view)

bot.run(os.environ["TOKEN"])
