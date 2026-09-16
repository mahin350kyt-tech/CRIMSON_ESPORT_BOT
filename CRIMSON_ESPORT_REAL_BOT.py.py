import os
import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

# These match the categories you showed. Change them if your exact names differ.
SUPPORT_CATEGORY_NAME = os.getenv("SUPPORT_CATEGORY_NAME", "Tickets")
RECRUITMENT_CATEGORY_NAME = os.getenv("RECRUITMENT_CATEGORY_NAME", "CANDIDATURE")

STAFF_ROLE_NAMES = [
    x.strip() for x in os.getenv(
        "STAFF_ROLE_NAMES", "STAFF,Directeur Exécutif"
    ).split(",") if x.strip()
]

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def find_category(guild, wanted_name):
    wanted = wanted_name.lower().strip()

    for category in guild.categories:
        if category.name.lower().strip() == wanted:
            return category

    # Useful for names such as "📩・CANDIDATURE..." where the exact
    # visible name may contain emojis.
    for category in guild.categories:
        if wanted in category.name.lower() or category.name.lower() in wanted:
            return category

    return None


def find_roles(guild, role_names):
    found = []
    for name in role_names:
        for role in guild.roles:
            if role.name.lower().strip() == name.lower().strip():
                found.append(role)
                break
    return found


def is_staff(member):
    return (
        member.guild_permissions.manage_channels
        or any(role.name in STAFF_ROLE_NAMES for role in member.roles)
    )


def ticket_channel_name(prefix, member):
    clean = re.sub(r"[^a-zA-Z0-9-]", "-", member.display_name.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")[:20]
    return f"{prefix}-{clean or member.id}"


async def create_ticket(interaction, ticket_type, prefix, category_name, role_names):
    guild = interaction.guild
    user = interaction.user

    if not guild or not isinstance(user, discord.Member):
        return await interaction.response.send_message(
            "❌ Cette action doit être utilisée dans un serveur.",
            ephemeral=True,
        )

    category = find_category(guild, category_name)
    if category is None:
        return await interaction.response.send_message(
            f"❌ Catégorie Discord introuvable : **{category_name}**\n"
            "Modifie `SUPPORT_CATEGORY_NAME` ou `RECRUITMENT_CATEGORY_NAME` dans `.env`.",
            ephemeral=True,
        )

    # One open ticket per user in that category.
    for channel in category.text_channels:
        if channel.topic and f"CRIMSON_OWNER:{user.id}" in channel.topic:
            return await interaction.response.send_message(
                f"❌ Tu as déjà un ticket ouvert : {channel.mention}",
                ephemeral=True,
            )

    staff_roles = find_roles(guild, role_names)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        ),
    }

    for role in staff_roles:
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
        )

    channel = await guild.create_text_channel(
        name=ticket_channel_name(prefix, user),
        category=category,
        overwrites=overwrites,
        topic=f"CRIMSON_OWNER:{user.id} | TYPE:{ticket_type}",
        reason=f"CRIMSON ticket - {ticket_type}",
    )

    embed = discord.Embed(
        title=f"🎫 {ticket_type}",
        description=(
            f"Bienvenue {user.mention} !\n\n"
            "Votre ticket a bien été créé.\n"
            "Le staff concerné va venir vous répondre.\n\n"
            "🔒 Quand votre demande est terminée, utilisez le bouton "
            "**Fermer le ticket**."
        ),
        color=discord.Color.from_rgb(220, 20, 60),
    )
    embed.set_footer(text="CRIMSON ESPORT")

    mentions = " ".join(role.mention for role in staff_roles)

    await channel.send(
        content=mentions or None,
        embed=embed,
        view=TicketButtons(),
        allowed_mentions=discord.AllowedMentions(roles=True, users=True),
    )

    await interaction.response.send_message(
        f"✅ Ticket créé : {channel.mention}",
        ephemeral=True,
    )


# ============================================================
# TICKET BUTTONS
# ============================================================

class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fermer le ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="crimson:close",
    )
    async def close_button(self, interaction, button):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ Salon invalide.", ephemeral=True
            )

        if not channel.topic or "CRIMSON_OWNER:" not in channel.topic:
            return await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket CRIMSON.",
                ephemeral=True,
            )

        if not is_staff(interaction.user):
            owner_id = channel.topic.split("CRIMSON_OWNER:", 1)[1].split(" ", 1)[0]
            if str(interaction.user.id) != owner_id:
                return await interaction.response.send_message(
                    "❌ Seul le propriétaire du ticket ou le staff peut le fermer.",
                    ephemeral=True,
                )

        await interaction.response.send_message(
            "🔒 Ticket fermé. Suppression dans **5 secondes**."
        )
        await discord.utils.sleep_until(
            discord.utils.utcnow() + timedelta(seconds=5)
        )
        await channel.delete(reason=f"CRIMSON ticket fermé par {interaction.user}")


# ============================================================
# SUPPORT DROPDOWN
# ============================================================

class SupportSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Choisis une catégorie",
            custom_id="crimson:support",
            options=[
                discord.SelectOption(
                    label="Support",
                    description="Question ou problème",
                    emoji="🎫",
                    value="support",
                ),
                discord.SelectOption(
                    label="Partenariat",
                    description="Sponsors et collaborations",
                    emoji="🤝",
                    value="partenariat",
                ),
                discord.SelectOption(
                    label="Signalement",
                    description="Signaler un problème",
                    emoji="⚠️",
                    value="signalement",
                ),
                discord.SelectOption(
                    label="Autre demande",
                    description="Toute autre demande",
                    emoji="📩",
                    value="autre",
                ),
            ],
        )

    async def callback(self, interaction):
        data = {
            "support": ("Support", "support"),
            "partenariat": ("Partenariat", "partenariat"),
            "signalement": ("Signalement", "signalement"),
            "autre": ("Autre demande", "demande"),
        }
        ticket_type, prefix = data[self.values[0]]

        role_env = {
            "support": "SUPPORT_ROLE_NAMES",
            "partenariat": "PARTNERSHIP_ROLE_NAMES",
            "signalement": "REPORT_ROLE_NAMES",
            "autre": "OTHER_SUPPORT_ROLE_NAMES",
        }
        roles = [
            x.strip() for x in os.getenv(
                role_env[self.values[0]],
                ",".join(STAFF_ROLE_NAMES),
            ).split(",") if x.strip()
        ]

        await create_ticket(
            interaction,
            ticket_type,
            prefix,
            SUPPORT_CATEGORY_NAME,
            roles,
        )


class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SupportSelect())


# ============================================================
# RECRUITMENT DROPDOWN
# ============================================================

class RecruitmentSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Choisis une catégorie",
            custom_id="crimson:recruitment",
            options=[
                discord.SelectOption(
                    label="Recrutement joueur",
                    description="Rejoindre un roster CRIMSON",
                    emoji="👤",
                    value="player",
                ),
                discord.SelectOption(
                    label="Recrutement joueuse / GC",
                    description="Rejoindre un roster féminin / GC",
                    emoji="👑",
                    value="female",
                ),
                discord.SelectOption(
                    label="Recrutement staff",
                    description="Rejoindre le staff CRIMSON",
                    emoji="🛡️",
                    value="staff",
                ),
                discord.SelectOption(
                    label="Recrutement coach",
                    description="Candidature coach",
                    emoji="🎓",
                    value="coach",
                ),
                discord.SelectOption(
                    label="Recrutement Rocket League",
                    description="Rejoindre un roster RL",
                    emoji="🚗",
                    value="rl",
                ),
            ],
        )

    async def callback(self, interaction):
        data = {
            "player": ("Recrutement joueur", "candidature"),
            "female": ("Recrutement joueuse / GC", "candidature"),
            "staff": ("Recrutement staff", "staff"),
            "coach": ("Recrutement coach", "coach"),
            "rl": ("Recrutement Rocket League", "rl-recrutement"),
        }

        ticket_type, prefix = data[self.values[0]]

        if self.values[0] == "staff":
            roles = os.getenv(
                "STAFF_RECRUITMENT_ROLE_NAMES",
                "Directeur Exécutif,STAFF",
            ).split(",")
        elif self.values[0] == "rl":
            roles = os.getenv(
                "RL_RECRUITMENT_ROLE_NAMES",
                ",".join(STAFF_ROLE_NAMES),
            ).split(",")
        else:
            roles = os.getenv(
                "PLAYER_RECRUITMENT_ROLE_NAMES",
                ",".join(STAFF_ROLE_NAMES),
            ).split(",")

        roles = [x.strip() for x in roles if x.strip()]

        await create_ticket(
            interaction,
            ticket_type,
            prefix,
            RECRUITMENT_CATEGORY_NAME,
            roles,
        )


class RecruitmentPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RecruitmentSelect())


# ============================================================
# PANEL EMBEDS
# ============================================================

def support_embed():
    embed = discord.Embed(
        description=(
            "Besoin d'aide ou envie de contacter le staff ?\n\n"
            "Choisis une catégorie :\n\n"
            "🎫 **Support**\n"
            "🤝 **Partenariat**\n"
            "⚠️ **Signalement**\n"
            "📩 **Autre demande**"
        ),
        color=discord.Color.from_rgb(220, 20, 60),
    )
    embed.set_footer(text="CRIMSON ESPORT")
    return embed


def recruitment_embed():
    embed = discord.Embed(
        description=(
            "Tu souhaites rejoindre CRIMSON ?\n\n"
            "Choisis le type de recrutement :\n\n"
            "👤 **Recrutement joueur**\n"
            "👑 **Recrutement joueuse / GC**\n"
            "🛡️ **Recrutement staff**\n"
            "🎓 **Recrutement coach**\n"
            "🚗 **Recrutement Rocket League**"
        ),
        color=discord.Color.from_rgb(220, 20, 60),
    )
    embed.set_footer(text="CRIMSON ESPORT")
    return embed


async def send_public_panel(interaction, embed, view, banner_filename, success_text):
    # The panel is public; the slash-command confirmation is PRIVATE.
    # This keeps the command itself from leaving an extra visible bot reply.
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Utilise cette commande dans un salon texte.", ephemeral=True
        )

    banner_path = os.path.join(os.path.dirname(__file__), banner_filename)
    if os.path.exists(banner_path):
        file = discord.File(banner_path, filename=banner_filename)
        embed.set_image(url=f"attachment://{banner_filename}")
        await interaction.channel.send(
            embed=embed,
            view=view,
            file=file,
        )
    else:
        await interaction.channel.send(embed=embed, view=view)

    await interaction.response.send_message(success_text, ephemeral=True)


# ============================================================
# PANEL COMMANDS
# ============================================================

@bot.tree.command(name="support", description="Envoyer le panneau CRIMSON SUPPORT")
@app_commands.checks.has_permissions(manage_guild=True)
async def support(interaction):
    await send_public_panel(
        interaction,
        support_embed(),
        SupportPanel(),
        "crimson_support_banner.png",
        "✅ Panneau CRIMSON SUPPORT envoyé.",
    )


@bot.tree.command(name="recruitment", description="Envoyer le panneau CRIMSON RECRUTEMENT")
@app_commands.checks.has_permissions(manage_guild=True)
async def recruitment(interaction):
    await send_public_panel(
        interaction,
        recruitment_embed(),
        RecruitmentPanel(),
        "crimson_recruitment_banner.png",
        "✅ Panneau CRIMSON RECRUTEMENT envoyé.",
    )


@bot.tree.command(name="ticket-panel", description="Envoyer le panneau support")
@app_commands.checks.has_permissions(manage_guild=True)
async def ticket_panel(interaction):
    await send_public_panel(
        interaction,
        support_embed(),
        SupportPanel(),
        "crimson_support_banner.png",
        "✅ Panneau CRIMSON SUPPORT envoyé.",
    )


@bot.tree.command(name="recruitment-panel", description="Envoyer le panneau recrutement")
@app_commands.checks.has_permissions(manage_guild=True)
async def recruitment_panel(interaction):
    await send_public_panel(
        interaction,
        recruitment_embed(),
        RecruitmentPanel(),
        "crimson_recruitment_banner.png",
        "✅ Panneau CRIMSON RECRUTEMENT envoyé.",
    )


@bot.tree.command(name="close", description="Fermer le ticket actuel")
async def close(interaction):
    channel = interaction.channel

    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    if not channel.topic or "CRIMSON_OWNER:" not in channel.topic:
        return await interaction.response.send_message(
            "❌ Ce salon n'est pas un ticket CRIMSON.",
            ephemeral=True,
        )

    if not is_staff(interaction.user):
        owner_id = channel.topic.split("CRIMSON_OWNER:", 1)[1].split(" ", 1)[0]
        if str(interaction.user.id) != owner_id:
            return await interaction.response.send_message(
                "❌ Staff ou propriétaire du ticket uniquement.",
                ephemeral=True,
            )

    await interaction.response.send_message("🔒 Ticket fermé.")
    await channel.delete(reason=f"CRIMSON ticket fermé par {interaction.user}")


@bot.tree.command(name="claim", description="Prendre en charge un ticket")
async def claim(interaction):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ Staff uniquement.", ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    if not interaction.channel.topic or "CRIMSON_OWNER:" not in interaction.channel.topic:
        return await interaction.response.send_message(
            "❌ Ce salon n'est pas un ticket CRIMSON.",
            ephemeral=True,
        )

    await interaction.response.send_message(
        f"🙋 Ticket pris en charge par {interaction.user.mention}."
    )


@bot.tree.command(name="rename", description="Renommer le ticket")
@app_commands.describe(name="Nouveau nom du ticket")
async def rename(interaction, name: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ Staff uniquement.", ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    if not interaction.channel.topic or "CRIMSON_OWNER:" not in interaction.channel.topic:
        return await interaction.response.send_message(
            "❌ Ce salon n'est pas un ticket CRIMSON.",
            ephemeral=True,
        )

    clean = re.sub(r"[^a-zA-Z0-9-]", "-", name.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")[:90]

    await interaction.channel.edit(name=clean)
    await interaction.response.send_message(f"✅ Ticket renommé en `{clean}`.")


@bot.tree.command(name="add", description="Ajouter un membre au ticket")
@app_commands.describe(member="Membre à ajouter")
async def add(interaction, member: discord.Member):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ Staff uniquement.", ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    if not interaction.channel.topic or "CRIMSON_OWNER:" not in interaction.channel.topic:
        return await interaction.response.send_message(
            "❌ Ce salon n'est pas un ticket CRIMSON.",
            ephemeral=True,
        )

    await interaction.channel.set_permissions(
        member,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
    )
    await interaction.response.send_message(
        f"✅ {member.mention} a été ajouté au ticket."
    )


@bot.tree.command(name="remove", description="Retirer un membre du ticket")
@app_commands.describe(member="Membre à retirer")
async def remove(interaction, member: discord.Member):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ Staff uniquement.", ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    await interaction.channel.set_permissions(member, overwrite=None)
    await interaction.response.send_message(
        f"✅ {member.mention} a été retiré du ticket."
    )


@bot.tree.command(name="lock", description="Verrouiller le ticket")
async def lock(interaction):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ Staff uniquement.", ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    owner_id = None
    if interaction.channel.topic and "CRIMSON_OWNER:" in interaction.channel.topic:
        owner_id = interaction.channel.topic.split("CRIMSON_OWNER:", 1)[1].split(" ", 1)[0]

    if owner_id:
        member = interaction.guild.get_member(int(owner_id))
        if member:
            await interaction.channel.set_permissions(member, send_messages=False)

    await interaction.response.send_message("🔒 Ticket verrouillé.")


@bot.tree.command(name="unlock", description="Déverrouiller le ticket")
async def unlock(interaction):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ Staff uniquement.", ephemeral=True
        )

    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    owner_id = None
    if interaction.channel.topic and "CRIMSON_OWNER:" in interaction.channel.topic:
        owner_id = interaction.channel.topic.split("CRIMSON_OWNER:", 1)[1].split(" ", 1)[0]

    if owner_id:
        member = interaction.guild.get_member(int(owner_id))
        if member:
            await interaction.channel.set_permissions(member, send_messages=True)

    await interaction.response.send_message("🔓 Ticket déverrouillé.")


# ============================================================
# MODERATION COMMANDS
# ============================================================

@bot.tree.command(name="clear", description="Supprimer des messages")
@app_commands.describe(amount="Nombre de messages (1 à 100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction, amount: app_commands.Range[int, 1, 100]):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ Salon invalide.", ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(
        f"🧹 {len(deleted)} messages supprimés.",
        ephemeral=True,
    )


@bot.tree.command(name="timeout", description="Mettre un membre en timeout")
@app_commands.describe(member="Membre", minutes="Durée en minutes")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 10080]):
    await member.timeout(
        discord.utils.utcnow() + timedelta(minutes=minutes),
        reason=f"Timeout par {interaction.user}",
    )
    await interaction.response.send_message(
        f"⏱️ {member.mention} timeout pendant **{minutes} min**."
    )


@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(member="Membre", reason="Raison")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction, member: discord.Member, reason: str = "Aucune raison"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} a été expulsé.")


@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(member="Membre", reason="Raison")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction, member: discord.Member, reason: str = "Aucune raison"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} a été banni.")


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():
    # Makes buttons/dropdowns continue working after a restart.
    bot.add_view(SupportPanel())
    bot.add_view(RecruitmentPanel())
    bot.add_view(TicketButtons())

    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)

            # The commands are defined globally in the code. Copy them to
            # the CRIMSON server first, then sync them there for fast testing.
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)

            print(f"[CRIMSON] {len(synced)} commandes synchronisées sur le serveur CRIMSON.")
        else:
            synced = await bot.tree.sync()
            print(f"[CRIMSON] {len(synced)} commandes globales synchronisées.")
    except Exception as e:
        print(f"[CRIMSON] Erreur sync: {e}")

    print(f"[CRIMSON] Bot connecté : {bot.user} ({bot.user.id})")


@bot.tree.error
async def command_error(interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        msg = "❌ Tu n'as pas la permission d'utiliser cette commande."
    else:
        print(f"[CRIMSON] Command error: {repr(error)}")
        msg = "❌ Une erreur est survenue. Regarde la console."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


bot.run(TOKEN)
