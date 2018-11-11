''' Helps with UI interactions '''
import asyncio

import discord

import mod.core.CONSTANTS as CONSTANTS


async def prompt_user(
	bot,
	ctx,
	title,
	description,
	options={},
	color=CONSTANTS.EMBED_COLOR_STANDARD,
	footer=''):
	''' Prompts the user for a choice. '''
	await prompt_user_raw(bot, ctx.channel, ctx.author, title, description,
		options, color, footer)


async def prompt_user_raw(
	bot,
	channel,
	subject_user,
	title,
	description,
	options={},
	color=CONSTANTS.EMBED_COLOR_STANDARD,
	footer=''):
	''' Prompts the user for a choice. '''
	embed = discord.Embed(
		title=title,
		colour=discord.Colour(color),
		description=description)

	embed.set_footer(text=footer)

	for option in options:
		embed.add_field(name=option['name'], value=option['value'], inline=False)

	msg = await channel.send(content='', embed=embed)

	if not options:
		return None  # No need to wait for responses if we're not expecting them.

	reactions = []

	for option in options:
		await msg.add_reaction(option['reaction'])
		reactions.append(option['reaction'])

	def check(reaction, user):
		return reaction in reactions and user.id == subject_user.id

	try:
		reaction, user = await bot.wait_for('reaction_add',
			timeout=60.0,
			check=check)
		for option in options:
			if option['reaction'] == reaction:
				return option['id']
	except asyncio.TimeoutError:
		return None
