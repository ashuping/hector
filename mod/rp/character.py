''' Speaking in-character '''

import random
import aiohttp

import discord
from discord.ext import commands

from sql.sql import sql_cur, sql_con
import mod.core.CONSTANTS as CONSTANTS
from mod.core.prompt import prompt_user, prompt_user_raw
from mod.rp.rp import RPError, RPManager


class AmbiguousCharacter(RPError):
	''' Raised when a character-name lookup returns multiple possibilities '''
	pass


def _fetch_character_by_name(user, character_name, db):
	''' Attempts to find a character by the given name '''
	with sql_cur(db) as cur:
		res = cur.execute('SELECT character_id, name, description, icon_url ' +
											'FROM characters ' +
											'WHERE owner_id=? AND LOWER(name)=LOWER(?);',
											(user.id, character_name)).fetchall()

	if not res:
		return None
	elif len(res) > 1:
		raise AmbiguousCharacter('Multiple characters named {n}.'.format(
			n=character_name))
	else:
		return {
			'id': res[0][0],
			'name': res[0][1],
			'description': res[0][2],
			'icon_url': res[0][3]
		}


def _fetch_character_by_id(character_id, db):
	''' Attempts to find a character with the given id '''
	with sql_cur(db) as cur:
		res = cur.execute('SELECT character_id, name, description, icon_url ' +
											'FROM characters ' +
											'WHERE character_id=?;',
											(character_id,)).fetchone()

	if not res:
		return None

	return {
		'id': res[0],
		'name': res[1],
		'description': res[2],
		'icon_url': res[3]
	}



def _fetch_webhook_for_channel(
	channel: discord.TextChannel,
	guild: discord.Guild,
	db):
	''' Fetches a webhook for a given channel '''
	with sql_cur(db) as cur:
		res = cur.execute('SELECT webhook_url FROM webhooks ' +
											'WHERE guild_id=? AND channel_id=?;',
											(guild.id, channel.id)).fetchone()

	if not res:
		return None
	return res[0]


def _fetch_preferred_character_for_channel(
	user: discord.Member,
	channel: discord.TextChannel,
	guild: discord.Guild,
	db):
	''' Gets an appropriate character, based on the user's favorites '''
	res = None

	with sql_cur(db) as cur:
		res = cur.execute('SELECT character_id, channel_id, guild_id ' +
											'FROM character_favorites ' +
											'WHERE user_id=?;', (user.id,)).fetchall()

	if not res:
		return None

	global_favorite = None
	guild_favorite = None
	channel_favorite = None

	for char in res:
		if char[1] == channel.id:  # Prefer channel favorites
			channel_favorite = char[0]
		elif char[2] == guild.id:  # Fall back to guild favorites
			guild_favorite = char[0]
		else:  # Least preferred are global favorites
			global_favorite = char[0]

	if channel_favorite:
		return _fetch_character_by_id(channel_favorite, db)
	elif guild_favorite:
		return _fetch_character_by_id(guild_favorite, db)
	elif global_favorite:
		return _fetch_character_by_id(global_favorite, db)
	else:
		return None


async def _say_in_character(ctx, char, message, db, embed=None):
	''' Says something in character '''
	await _say_in_character_raw(ctx.channel, ctx.guild, char, message, db, embed)

async def _say_in_character_raw(channel, guild, char, message, db, embed=None):
	''' Says something in character '''
	hook_url = _fetch_webhook_for_channel(channel, guild, db)

	if not hook_url:
		raise commands.BadArgument('No webhook for this channel. ' +
																'Use `hook <webhook url>` to set the hook.')

	async with aiohttp.ClientSession() as session:
		hook = discord.Webhook.from_url(hook_url,
			adapter=discord.AsyncWebhookAdapter(session))
		if char['icon_url']:
			await hook.send(
				message,
				username=char['name'],
				embed=embed,
				avatar_url=char['icon_url'])
		else:
			await hook.send(message, username=char['name'], embed=embed)


class Character:
	''' Commands for speaking in-character '''
	def __init__(self, bot, db_handle):
		self.bot = bot
		self.db = db_handle

	async def on_message(self, message):
		''' Auto-in-character '''
		if message.author.bot:
			return  # do not attempt to in-character bots.

		acceptable_starters = 'abcdefghijklmnopqrstuvwxyz1234567890"\'`'
		if not message.content[0].lower() in acceptable_starters:
			return  # only auto-char if the message doesn't start with a special char
			#       # (that way, we don't interfere with bot commands, OOC, etc.

		r = RPManager(self.bot, self.db)
		region = await r._get_region(message.guild.id, message.channel.id)
		if not region:  # only auto-char in regions
			return

		if region['status'] != 0:  # only auto-char if the region is active
			return

		char_to_use = _fetch_preferred_character_for_channel(
			message.author,
			message.channel,
			message.guild,
			self.db)

		if not char_to_use:
			dm_channel = message.author.dm_channel
			if not dm_channel:
				dm_channel = await message.author.create_dm()

			await prompt_user_raw(self.bot, dm_channel, message.author,
				'{i} Notice'.format(i=CONSTANTS.REACTION_ERROR),
				'It looks like you\'re sending messages to an in-character channel ' +
				'({c} on {g}), '.format(
					c=message.channel.name,
					g=message.guild.name) +
				'but you haven\'t set a favorite character yet. Try running ' +
				'`{p}favorite <name>` in the channel '.format(
					p=self.bot.command_prefix) +
				'to set your preferred character.',
				color=CONSTANTS.EMBED_COLOR_ERROR)
		else:
			await message.delete()
			await _say_in_character_raw(
				message.channel,
				message.guild,
				char_to_use,
				message.content,
				self.db)

	@commands.command()
	async def sayas(self, ctx, character, *, message):
		''' Say something in-character '''
		char = _fetch_character_by_name(ctx.message.author, character, self.db)

		if not char:
			await ctx.send('No character "{c}" found.'.format(c=character))
		else:
			await _say_in_character(ctx, char, message, self.db)
			await ctx.message.delete()

	@commands.command()
	async def sudo(self, ctx, user: discord.Member, *, message):
		''' Impersonate another user '''
		await ctx.send('Asked to say {m} as {u}.'.format(m=message, u=user))
		await _say_in_character(ctx, {'name': user.name, 'id': 0}, message, self.db)

	@commands.command()
	async def hook(self, ctx, webhook_url):
		''' Set the webhook URL for a channel '''
		with sql_cur(self.db) as cur:
			cur.execute('INSERT INTO webhooks (guild_id, channel_id, webhook_url)' +
									'VALUES (?,?,?)' +
									'ON CONFLICT (channel_id)' +
									'DO UPDATE SET webhook_url=EXCLUDED.webhook_url;',
									(ctx.guild.id, ctx.channel.id, webhook_url))
		await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)

	@commands.group()
	async def character(self, ctx):
		''' Character-based commands '''
		# await ctx.send('Try `help character` for more information.')
		pass

	@character.command()
	async def add(self, ctx, *, name):
		''' Adds a new character '''
		with sql_cur(self.db) as cur:
			cur.execute('INSERT INTO characters (character_id, owner_id, name, ' +
									'description, icon_url) ' +
									'VALUES (?,?,?,?,?)',
									(random.randint(1, 9223372036854775807),
									ctx.message.author.id,
									name,
									'Run `character describe <name> <description> ' +
										'to set description',
									''))

		await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)

	@character.command()
	async def describe(self, ctx, char_name, *, description):
		''' Adds a description to a character '''
		char = _fetch_character_by_name(ctx.message.author, char_name, self.db)

		with sql_cur(self.db) as cur:
			cur.execute('UPDATE characters ' +
									'SET description=? ' +
									'WHERE character_id=?;',
									(description,
									char['id']))
		await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)

	@character.command()
	async def icon(self, ctx, char_name, icon_url):
		''' Sets the avatar icon for a character '''
		char = _fetch_character_by_name(ctx.message.author, char_name, self.db)

		with sql_cur(self.db) as cur:
			cur.execute('UPDATE characters ' +
									'SET icon_url=? ' +
									'WHERE character_id=?;',
									(icon_url,
									char['id']))
		await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)

	@character.command()
	async def list(self, ctx, user: discord.Member = None):
		''' Returns a list of your (or another user's) characters '''
		if not user:
			user = ctx.message.author

		with sql_cur(self.db) as cur:
			res = cur.execute('SELECT character_id, name, description ' +
												'FROM characters ' +
												'WHERE owner_id=?;',
												(user.id,)).fetchall()

		if not res:
			await ctx.send('No characters found for {u}.'.format(u=user.name))

		else:
			lst = 'Characters for {u}:'.format(u=user.name)
			for char in res:
				lst = lst + '\n[{cid}] - **{name}** - *{desc}*'.format(
					cid=char[0],
					name=char[1],
					desc=char[2])

			await ctx.send(lst)

	@character.command()
	async def favorite(self, ctx, character_name):
		''' Adds a favorite character for the given channel '''
		character = _fetch_character_by_name(
			ctx.message.author,
			character_name,
			self.db)

		with sql_cur(self.db) as cur:
			cur.execute('INSERT INTO character_favorites (character_id, user_id, ' +
									'channel_id, guild_id) ' +
									'VALUES (?,?,?,?) ' +
									'ON CONFLICT (channel_id) ' +
									'DO UPDATE SET channel_id=EXCLUDED.channel_id, ' +
									'guild_id=EXCLUDED.guild_id;',
									(character['id'],
										ctx.message.author.id,
										ctx.channel.id,
										ctx.guild.id))
		await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)

	@character.command()
	async def transfer(self, ctx, char_name, new_owner: discord.Member):
		''' Transfers a character to a new owner '''
		char = _fetch_character_by_name(ctx.message.author, char_name, self.db)

		with sql_cur(self.db) as cur:
			cur.execute('UPDATE characters ' +
									'SET owner_id=? ' +
									'WHERE character_id=?;',
									(new_owner.id,
									char['id']))
		await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)


def setup(bot):
	''' Add cog to bot '''
	bot.add_cog(Character(bot, sql_con()))
