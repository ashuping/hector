''' Detecting die rolls '''

import discord
from discord.ext import commands

from sql.sql import sql_con

import mod.core.CONSTANTS as CONSTANTS
from mod.core.prompt import prompt_user_raw
from mod.roll.expressions import Expression, find_first_of,\
	ExpressionSyntaxError, ExpressionVariableError

class DieRoll:
	''' Handle die rolls '''
	def __init__(self, bot, db):
		self.bot = bot
		self.db = db

	async def on_message(self, message):
		''' Parse all expressions '''
		if message.author.bot:
			return  # do not attempt to roll for bots

		expressions = []
		keywords = ['[[', ']]']
		start_dex = 0
		offset = 0
		level = 0
		while True:
			wrds = find_first_of(message.content, keywords, offset)
			dex = wrds[0]
			kwrd = wrds[1]
			# print('level {l} str {s} <{t}|{u}|> {v}'.format(
			# 	l=level,
			# 	s=message.content[:start_dex],
			# 	t=message.content[start_dex:dex],
			# 	u=message.content[dex:dex+2],
			# 	v=message.content[dex+2:]))

			if kwrd == '[[':
				if level == 0:
					start_dex = dex
				level = level + 1
				offset = dex + 2

			elif kwrd == ']]':
				level = level - 1
				offset = dex + 2

				if level == 0:
					level = 0
					# print('	found candidate expression {e}'.format(
					# 	e=message.content[start_dex:dex+2]))
					expressions.append(message.content[start_dex:dex + 2])

				elif level < 0:
					level = 0

			else:
				break

		results = []
		for exp in expressions:
			mexp = ''
			for c in exp:
				if c != ' ':
					mexp = mexp + c  # strip spaces
			try:
				numerical_result = Expression(mexp).run()
				results.append([exp, numerical_result])
			except ExpressionSyntaxError as e:
				dm_channel = message.author.dm_channel
				if not dm_channel:
					dm_channel = await message.author.create_dm()

				await prompt_user_raw(self.bot, dm_channel, message.author,
					'{i} Notice'.format(i=CONSTANTS.REACTION_ERROR),
					'`{d}` is not valid die syntax.\n(error {er})'.format(
						d=exp,
						er=str(e)),
					color=CONSTANTS.EMBED_COLOR_ERROR)

			except ExpressionVariableError as e:
				dm_channel = message.author.dm_channel
				if not dm_channel:
					dm_channel = await message.author.create_dm()

				await prompt_user_raw(self.bot, dm_channel, message.author,
					'{i} Notice'.format(i=CONSTANTS.REACTION_ERROR),
					'`{d}` is not valid die syntax.\n(variable error {er})'.format(
						d=exp,
						er=str(e)),
					color=CONSTANTS.EMBED_COLOR_ERROR)

		desc = ''
		for res in results:
			desc = desc + ('\n' +
				'`{raw}` -> {num}'.format(
					raw=res[0],
					num=res[1]))

		embed = discord.Embed(
			title='{i} Die roll'.format(i=CONSTANTS.REACTION_DIE_ROLL),
			colour=discord.Colour(CONSTANTS.EMBED_COLOR_STANDARD),
			description=desc)

		embed.set_footer(text='all die results {chk} guaranteed '.format(
				chk=CONSTANTS.REACTION_CHECK) +
			'biased in the dm\'s favor')

		await message.channel.send(content='', embed=embed)


def setup(bot):
	''' Add cog to bot '''
	bot.add_cog(DieRoll(bot, sql_con()))
