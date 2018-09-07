import random
from asyncio import TimeoutError

import discord
from discord.ext import commands

import mod.core.permissions as permissions
from mod.core.messages import track
from sql.sql import sql_cur, sql_con

class RPError(discord.ext.commands.CommandError):
	pass

class InvalidRegionError(RPError):
	pass

class RPManager:
	''' RP channel management '''
	def __init__(self, bot, db_handle):
		self.bot = bot
		self.db = db_handle
	

	async def _list_regions(self, guild_id=None):
		regions = []
		query = 'SELECT channel_id, guild_id, name, description, status, active_category FROM regions'
		if guild_id:
			query = query + ' WHERE guild_id=?;'
		else:
			query = query + ';'

		with sql_cur(self.db) as cur:
			if guild_id:
				cur.execute(query,(guild_id,))
			else:
				cur.execute(query)
			for region in cur.fetchall():
				regions.append({'channel_id':region[0],'guild_id':region[1],'name':region[2],'description':region[3],'status':region[4], 'active_category':region[5]})

		return regions
	

	async def _get_region(self, guild_id, channel_id):
		regions = await self._list_regions(guild_id)
		for region in regions:
			if region['channel_id'] == channel_id:
				return region

		return None
	

	async def _decode_status(self, status_id):
		if status_id == 0:
			return 'ACTIVE'
		elif status_id == 1:
			return 'INACTIVE'
		elif status_id == 2:
			return 'PAUSED'
		else:
			return '<INVALID STATUS>'


	def _validate_name(self, guild, name):
		if not name:
			return False
		
		sanitized_name = self._sanitize_channel_name(name)
		if len(sanitized_name) == 0:
			return False

		for channel in guild.channels:
			if channel.name == sanitized_name:
				return False

		return True


	def _sanitize_channel_name(self, channel_name):
		lower_name = channel_name.lower()
		presanitized_name = ''
		for character in lower_name:
			if character not in 'abcdefghijklmnopqrstuvwxyz1234567890':
				presanitized_name = presanitized_name + '-'
			else:
				presanitized_name = presanitized_name + character


		sanitized_name = ''
		last_character = None
		for character in presanitized_name:
			if character == '-':
				if last_character:
					if last_character != '-':
						sanitized_name = sanitized_name + character
						last_character = character
			else:
				sanitized_name = sanitized_name + character
				last_character = character

		if sanitized_name[-1:] == '-':
			sanitized_name = sanitized_name[:-1]
	

		return sanitized_name


	async def _generate_topic(self, region_meta):
		return '{0} | {1} | STATUS: {2} | Managed by Hector'.format(region_meta['name'], region_meta['description'], await self._decode_status(region_meta['status']))


	async def _refresh_region_meta(self, region_meta):
		region = self.bot.get_channel(region_meta['channel_id'])
		if not region:
			with sql_cur(self.db) as cur:
				cur.execute('DELETE FROM regions WHERE channel_id=?',(region_meta['channel_id'],))
				raise commands.CheckFailure('Channel for region {0} is missing! Removed associated region data.')
		channel_category_id = None
		if region_meta['status'] != 1:
			channel_category_id = region_meta['active_category']
		else:
			with sql_cur(self.db) as cur:
				cur.execute('SELECT inactive_category FROM guild_settings WHERE guild_id=?',(region.guild.id,))
				row = cur.fetchone()
				if not row:
					raise commands.BadArgument('Please use the {0}rpset inactive command to set up a channel category for inactive channels. {0}help rpset inactive for more information.'.format(self.bot.command_prefix))
				channel_category_id = row[0]
		channel_category = None
		for category in region.guild.categories:
			if category.id == channel_category_id:
				channel_category = category

		await region.edit(name=self._sanitize_channel_name(region_meta['name']), position=0, nsfw=region.is_nsfw(), topic=await self._generate_topic(region_meta), sync_permissions=True, category=channel_category, reason='Updating RP region metadata.')
		await self._edit_region(region_meta)


	async def _generate_region(self, guild, name="Unnamed Region", description="Use the ``describe`` command in this channel to edit the region description.", active_category=None, existing_channel=None, status_override=1):
		new_region = None
		if not existing_channel:
			if not self._validate_name(guild, name):
				raise commands.BadArgument('Channel name is not valid, or another channel with that name already exists.')
			new_region = await guild.create_text_channel(name=self._sanitize_channel_name(name))
		else:
			new_region = existing_channel
		region_meta = {'channel_id':new_region.id,'guild_id':guild.id,'name':name,'description':description,'status':status_override,'active_category':active_category}
		await self._refresh_region_meta(region_meta)
		return region_meta


	async def _edit_region(self, region):
		with sql_cur(self.db) as cur:
			cur.execute('SELECT name FROM regions WHERE channel_id=? AND guild_id=?;',(region['channel_id'],region['guild_id']))
			if len(cur.fetchall()) == 0:
				cur.execute('INSERT INTO regions (channel_id, guild_id, name, description, status, active_category) VALUES (?,?,?,?,?,?);',(region['channel_id'],region['guild_id'],region['name'],region['description'],region['status'],region['active_category']))
			else:
				cur.execute('UPDATE regions SET name=?,description=?,status=?,active_category=? WHERE channel_id=? AND guild_id=?;',(region['name'],region['description'],region['status'],region['active_category'],region['channel_id'],region['guild_id']))

	
	@commands.group()
	@permissions.require(permissions.manage)
	async def rpset(self, ctx):
		''' (Chanop-only) Change server settings related to the RP module '''
		pass
	
	@rpset.command(name="inactive")
	async def set_inactive(self, ctx):
		''' Set the category where inactive region channels are stored '''
		with sql_cur(self.db) as cur:
			cur.execute('SELECT inactive_category FROM guild_settings WHERE guild_id=?;',(ctx.guild.id,))
			if cur.fetchone():
				cur.execute('UPDATE guild_settings SET inactive_category=? WHERE guild_id=?;',(ctx.channel.category_id, ctx.guild.id))
			else:
				cur.execute('INSERT INTO guild_settings (guild_id, inactive_category) VALUES (?,?);',(ctx.guild.id, ctx.channel.category_id))

		await ctx.message.add_reaction('✅')

	@commands.command()
	@permissions.require(permissions.p_open)
	async def open(self, ctx, *location_raw):
		''' Opens a region (chanops can use this to make new regions) '''
		regions = await self._list_regions(ctx.guild.id)
		regions_filtered = []
		final_region = None
		location = ''
		for piece in location_raw:
			# Put checks for switches, etc. here
			location = location + piece + ' '

		location = location.strip()

		for region in regions:
			if self._sanitize_channel_name(location) in self._sanitize_channel_name(region['name'].strip()):
				regions_filtered.append(region)

		if len(location) == 0:
			region = await self._get_region(ctx.guild.id, ctx.channel.id)
			if not region:
				raise commands.BadArgument('No region name provided and this channel is not a region! Use {0}makeregion to convert.'.format(self.bot.command_prefix))
			else:
				final_region = region
		elif len(regions_filtered) == 0:
			if await permissions.has_permission(ctx, permissions.create_new):
				msg = await ctx.send('No region found. Press ✳️ within 10 seconds to create a new region.')
				await msg.add_reaction('\u2733')

				def check(reaction, user):
					return user == ctx.message.author and str(reaction.emoji) == '\u2733' and reaction.message.id == msg.id

				try:
					reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)

				except TimeoutError:
					await msg.clear_reactions()
					await msg.edit(content='No region found.')
					await track(msg, ctx.author)
					return

				else:
					await msg.clear_reactions()
					await msg.edit(content='Confirmed. Generating new region ``{0}`` (sanitized name ``#{1}``)...'.format(location, self._sanitize_channel_name(location)))
					final_region = await self._generate_region(ctx.guild, location, active_category=ctx.message.channel.category_id, status_override=0)
					final_region_chan = ctx.guild.get_channel(final_region['channel_id'])


					await msg.edit(content='Successfully generated new region ``{0}``. Please drag the channel to the desired start category, then press ✳️. (5-minute timeout)'.format(location))
					await msg.add_reaction('\u2733')
					try:
						reaction, user = await self.bot.wait_for('reaction_add', timeout=300, check=check)

					except TimeoutError:
						pass

					finally:
						final_region['active_category'] = final_region_chan.category_id
						response = ''
						if final_region_chan.category:
							response = 'Set category for {0} to {1}.'.format(final_region['name'],final_region['active_category'])
						else:
							response = '{0} will have no category.'.format(final_region['name'])

						await self._refresh_region_meta(final_region)
						await msg.clear_reactions()
						await msg.edit(content=response)

						
					await ctx.message.add_reaction('✅')
					await track(msg, ctx.author)

			else:
				msg = await ctx.send('No region found. Use {0}list to list regions, or ask a chanop for help.'.format(self.bot.command_prefix))
				await track(msg, ctx.author)
				await ctx.message.add_reaction('❓')
				return

		elif len(regions_filtered) > 1:
			tex = 'Ambiguous input. Matching channels:\n```\n'
			num_processed = 0
			for region in regions_filtered:
				to_check = tex + '"{0}" id {1}\n'.format(region['name'],region['channel_id'])
				if len(to_check) > 1800:
					tex = tex + '...[{0} more]'.format(len(regions_filtered) - num_processed)
				else:
					num_processed = num_processed + 1
					tex = to_check

			msg = await ctx.send(tex+'```')
			await track(msg, ctx.author)
			await ctx.message.add_reaction('❓')
			return

		else:
			final_region = regions_filtered[0]
			await ctx.message.add_reaction('✅')
		
		final_region['status'] = 0
		await self._refresh_region_meta(final_region)
		final_msg = await ctx.send('Region {0} opened in channel {1}.'.format(final_region['name'],self._sanitize_channel_name(final_region['name'])))
		regional_channel = ctx.guild.get_channel(final_region['channel_id'])
		final_msg_2 = await regional_channel.send('Region {0} is now open, {1}.'.format(final_region['name'],ctx.author.mention))
		await track(final_msg, ctx.author)
		await track(final_msg_2, ctx.author)
	

	@commands.command(name='makeregion')
	@permissions.require(permissions.convert)
	async def make_region(self, ctx, *, name=None):
		''' Converts an existing channel into a Hector region. '''
		if not name:
			raise commands.BadArgument('Please name the new Region.')
		if await self._get_region(ctx.guild.id, ctx.channel.id):
			raise commands.CheckFailure('Channel #{0} is already a region!'.format(ctx.channel.name))
		
		if ctx.channel.topic:
			await self._generate_region(ctx.guild, name, description=ctx.channel.topic, active_category=ctx.channel.category_id, existing_channel=ctx.channel)
		else:
			await self._generate_region(ctx.guild, name, active_category=ctx.channel.category_id, existing_channel=ctx.channel)
		await ctx.message.add_reaction('✅')
	
	@commands.command(name='unregion')
	@permissions.require(permissions.unmake)
	async def unmake_region(self, ctx):
		''' Removes Hector region status from the channel
		  ' (Note: this does not delete the channel itself)
		'''
		region = await self._get_region(ctx.guild.id, ctx.channel.id)
		
		if not region:
			raise commands.CheckFailure('Channel #{0} is not a region!'.format(ctx.channel.name))

		with sql_cur(self.db) as cur:
			cur.execute('DELETE FROM regions WHERE channel_id=?;', (ctx.channel.id,))

		await ctx.message.add_reaction('✅')
	
	@commands.command()
	@permissions.require(permissions.move)
	async def move(self, ctx, channel: discord.TextChannel=None):
		''' Changes the category where an RP channel moves to when it is active. '''
		if not channel:
			channel = ctx.channel

		target_region = await self._get_region(ctx.guild.id, channel.id)
		if not target_region:
			raise commands.CheckFailure('Channel #{0} has no associated Region!'.format(ctx.channel.name))

		msg = await ctx.send('Move the channel to the desired target category. When finished, press \u2733. (this command times out in 5 minutes)')

		def check(reaction, user):
			return user == ctx.message.author and str(reaction.emoji) == '\u2733' and reaction.message.id == msg.id

		await msg.add_reaction('\u2733')
		try:
			reaction, user = await self.bot.wait_for('reaction_add', timeout=300, check=check)

		except TimeoutError:
			pass

		finally:
			target_region['active_category'] = channel.category_id
			response = ''
			if ctx.channel.category_id:
				response = 'Set category for {0} to {1}.'.format(target_region['name'],target_region['active_category'])
			else:
				response = '{0} will have no category.'.format(target_region['name'])

			await self._refresh_region_meta(target_region)
			await msg.clear_reactions()
			await msg.edit(content=response)
			await track(msg, ctx.author)

	@commands.command()
	@permissions.require(permissions.describe)
	async def describe(self, ctx, *, description):
		''' Change the description for a region. '''
		target_region = await self._get_region(ctx.guild.id, ctx.channel.id)
		if not target_region:
			raise commands.CheckFailure('Channel #{0} has no associate Region!'.format(ctx.channel.name))

		target_region['description'] = str(description)

		await self._refresh_region_meta(target_region)
		await ctx.message.add_reaction('✅')
	

	@commands.command()
	async def fix(self, ctx, channel: discord.TextChannel = None):
		''' Updates a location's channel (i.e. category, permissions, etc.) '''
		if not channel:
			channel = ctx.channel

		channel_meta = await self._get_region(ctx.guild.id, channel.id)
		if not channel_meta:
			raise commands.BadArgument('Channel #{0} has no associated region!'.format(channel.name))
		else:
			await self._refresh_region_meta(channel_meta)
			await ctx.message.add_reaction('✅')

	
	@commands.command()
	@permissions.require(permissions.close)
	async def close(self, ctx, *location_raw):
		''' Closes a region and moves it to the inactive category. '''
		regions = await self._list_regions(ctx.guild.id)
		regions_filtered = []
		final_region = None
		location = ''
		for piece in location_raw:
			# Put checks for switches, etc. here
			location = location + piece + ' '

		location = location.strip()

		for region in regions:
			if location in region['name'].strip().lower():
				regions_filtered.append(region)
		
		if len(location) == 0:
			region = await self._get_region(ctx.guild.id, ctx.channel.id)
			if not region:
				raise commands.BadArgument('No region name provided, and this channel has no associated region!')
			else:
				final_region = region
		elif len(regions_filtered) == 0:
			raise commands.BadArgument('No regions matching query "{0}"'.format(location))
		elif len(regions_filtered) > 1:
			tex = 'Ambiguous input. Matching channels:\n```\n'
			num_processed = 0
			for region in regions_filtered:
				to_check = tex + '"{0}" id {1}\n'.format(region['name'],region['channel_id'])
				if len(to_check) > 1800:
					tex = tex + '...[{0} more]'.format(len(regions_filtered) - num_processed)
				else:
					num_processed = num_processed + 1
					tex = to_check

			msg = await ctx.send(tex+'```')
			await track(msg, ctx.author)
			await ctx.message.add_reaction('❓')
			return
		else:
			final_region = regions_filtered[0]

		if final_region['status'] == 1:
			raise commands.BadArgument('Region {0} is already closed.'.format(region['name']))
		else:
			final_region['status'] = 1
			await self._refresh_region_meta(final_region)
			await ctx.message.add_reaction('✅')


	@commands.command()
	async def list(self, ctx, offset='0'):
		''' Provides a list of regions present on this server.
		  ' :param offset: optional parameter to start the list at the <offset>'th region.
		'''
		regions = await self._list_regions(ctx.guild.id)
		num_offset = 0
		if offset[0] == '+':
			num_offset = int(offset[1:])
		else:
			num_offset = int(offset)

		tex = 'Regions on this server:\n```\n'
		num_processed = 0
		for region in regions:
			if num_processed < num_offset:
				num_processed = num_processed + 1
				continue
			to_check = tex + '{0:03d}| "{1}" id {2}\n'.format(num_processed,region['name'],region['channel_id'])
			if len(to_check) > 1800:
				tex = tex + '...[{0} more]({1}list +{2} for more)'.format(len(regions) - (num_processed), self.bot.command_prefix, num_processed)
				break
			else:
				num_processed = num_processed + 1
				tex = to_check
		
		msg = await ctx.send(tex + '```')
		await track(msg, ctx.author)

					

def setup(bot):
	bot.add_cog(RPManager(bot, sql_con()))
