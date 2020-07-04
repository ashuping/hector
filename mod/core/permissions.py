from asyncio import TimeoutError
import json

import discord
from discord.ext import commands
from discord import Member, Role

import mod.core.CONSTANTS as CONSTANTS
from sql.sql import sql_cur, sql_con
from mod.core.messages import track

''' -----Permission offsets----- '''
# Note: each permission has a corresponding 'deny' flag at <code>+1, e.g.
# 'deny_p_open' is flag 1. Setting the deny flag for a permission means that
# users will not get the permission even if a lower role (on the role list)
# would otherwise grant it. Setting the grant flag on a higher role overrides
# deny flags on lower roles.

# Note that guild administrators bypass this permission system entirely.

p_open     =  0 # Open regions
close      =  2 # Close regions
create_new =  4 # Create new regions (from scratch - this does not permit converting existing channels into regions)
describe   =  6 # Change region descriptions
move       =  8 # Move regions to new categories 
convert    = 10 # Convert existing channels into regions
unmake     = 12 # Remove region status from channels
manage     = 14 # Manage server defaults and role permissions

_perms_lut  = {'p_open':p_open,'open':p_open,'close':close,'create_new':create_new,'create':create_new,'describe':describe,'move':move,'convert':convert,'unmake':unmake,'manage':manage}

_perms_lut_unaliased = {'Open regions':p_open,'Close regions':close,'Create new regions':create_new,'Change region descriptions':describe,'Change region categories':move,'Convert existing channels into regions':convert,'Unmake regions':unmake,'Manage permissions and server settings':manage}

def require(perm):
	async def wrapper(ctx):
		return await has_permission(ctx, perm)
	return commands.check(wrapper)

def _has(code, permission):
	return (code >> permission) % 2 == 1

def _denied(code, permission):
	return (code >> (permission+1)) % 2 == 1

def _grant_perm(code, perm):
	return (code | (1 << perm)) & ~(1 << (perm+1))

def _deny_perm(code, perm):
	return (code | (1 << (perm+1))) & ~(1 << perm)

def _clear_perm(code, perm):
	return (code & ~(1 << (perm))) & ~(1 << (perm+1))

def _to_string(code):
	global _perms_lut_unaliased
	for key,val in _perms_lut_unaliased.items():
		if val == code:
			return key
	
	return None

def _string_convert(perm_string):
	global _perms_lut
	if not perm_string.lower() in _perms_lut.keys():
		return None
	else:
		return _perms_lut[perm_string.lower()]

def _construct_from_preset_string(preset_string):
	role_perms = 0
	for perm_s, val in preset_string.items():
		perm = _string_convert(perm_s)
		if perm == None:
			raise commands.CheckFailure('Malformed JSON preset: unknown permission name {0} in preset string {1}.'.format(perm_s, preset_string))

		if val == 'GRANT':
			role_perms = _grant_perm(role_perms, perm)
		elif val == 'DENY':
			role_perms = _deny_perm(role_perms, perm)
		else:
			raise commands.CheckFailure('Malformed JSON preset: unknown permission mode {0} (must be GRANT or DENY).'.format(perm))
	
	return role_perms

def _perms_combine(high_priority, low_priority):
	final_perm = 0
	for perm in _perms_lut.values():
		if _denied(high_priority, perm):
			final_perm = _deny_perm(final_perm, perm)
		elif _has(low_priority, perm) or _has(high_priority, perm):
			final_perm = _grant_perm(final_perm, perm)
		elif _denied(low_priority, perm):
			final_perm = _deny_perm(final_perm, perm)
	
	return final_perm

class Permissions(commands.Cog):
	''' Manages user permissions '''
	def __init__(self, bot):
		self.bot = bot
		self.db = sql_con()

		self._GRANT = 0
		self._DENY = 1
		self._CLEAR = 2
		self._OVERWRITE = 3


	def _perms_write(self, guild_id, role_id, perms):
		with sql_cur(self.db) as cur:
			cur.execute('SELECT permissions FROM permissions WHERE guild_id=? AND role_id=?;', (guild_id, role_id))
			res = cur.fetchone()

			if res:
				cur.execute('UPDATE permissions SET permissions=? WHERE guild_id=? AND role_id=?', (perms, guild_id, role_id))

			else:
				cur.execute('INSERT INTO permissions (guild_id, role_id, permissions) VALUES (?,?,?);', (guild_id, role_id, perms))


	def _perms_set(self, guild_id, role_id, permissions, mode=None):
		if not mode:
			mode = self._GRANT

		current_perms = 0
		with sql_cur(self.db) as cur:
			cur.execute('SELECT permissions FROM permissions WHERE guild_id=? AND role_id=?;', (guild_id, role_id))
			res = cur.fetchone()
			if res:
				current_perms = res[0]
				
		new_perms = current_perms
		for perm in permissions:
			if mode == self._DENY:
				if _has(new_perms, perm) or not _denied(new_perms, perm):
					new_perms = _deny_perm(new_perms, perm)

			elif mode == self._GRANT:
				if _denied(new_perms, perm) or not _has(new_perms, perm):
					new_perms = _grant_perm(new_perms, perm)

			elif mode == self._CLEAR:
				if _has(new_perms, perm) or _denied(new_perms, perm):
					new_perms = _clear_perm(new_perms, perm)
			
			else:
				raise commands.CommandError('Unknown value {0} for permission mode enum.'.format(mode))
		
		self._perms_write(guild_id, role_id, new_perms)

	@require(manage)
	@commands.group()
	async def perms(self, ctx):
		''' (Manage-Perms-Only) Administrator commands for managing permissions '''
		pass

	async def change(self, ctx, role: Role, *permission_names, mode=None):
		if not mode:
			mode = self._GRANT
		if not role:
			raise commands.BadArgument('Please provide a valid role name.')

		extant_permissions = []
		unknown_permissions = []
		for perm_name in permission_names[0]:
			perm = _string_convert(perm_name)
			if perm == None:
				unknown_permissions.append(perm_name)
			else:
				extant_permissions.append(perm)

		if len(extant_permissions) == 0:
			if len(unknown_permissions) == 0:
				raise commands.BadArgument('Please provide one or more permissions to add to the {0} role.'.format(role.name))
			else:
				raise commands.BadArgument('Role(s) {0} is/are not valid.'.format(unknown_permissions))
		else:
			if len(unknown_permissions) != 0:
				warn_msg = await ctx.send('Warning: Permission(s) {0} not found. Skipping these permissions.'.format(unknown_permissions))
				await track(warn_msg)

			self._perms_set(ctx.guild.id, role.id, extant_permissions, mode=mode)

			await ctx.message.add_reaction(CONSTANTS.REACTION_CHECK)

	@perms.command()
	async def grant(self, ctx, role: Role, *permission_names):
		''' Adds a permission to a role. 
		  ' Note that this overrides denied permissions for lower roles.
		'''
		await self.change(ctx, role, permission_names, mode=self._GRANT)
	
	@perms.command()
	async def deny(self, ctx, role: Role, *permission_names):
		''' Denies a permission to a role.
		  ' Note that this overrides granted permissions for lower roles.
		'''
		await self.change(ctx, role, permission_names, mode=self._DENY)
	
	@perms.command()
	async def clear(self, ctx, role: Role, *permission_names):
		''' Clears a permission (makes it neither granted nor denied) for a role.
		  ' This is not the same as denying the permission, as it does not
			' override lower roles which grant the permission.
		'''
		await self.change(ctx, role, permission_names, mode=self._CLEAR)

	@perms.command(name='listperms')
	async def list_perissions(self, ctx):
		''' Returns a list of possible permissions. '''
		global _perms_lut_unaliased
		global _perms_lut
		perm_list = 'Permissions:```\n'
		for key,val in _perms_lut_unaliased.items():
			perm_keyword = ''
			for pkey,pval in _perms_lut.items():
				if pval == val:
					perm_keyword = pkey
					break
			perm_list = perm_list + '{0} ({1})\n'.format(perm_keyword,key)
		perm_list = perm_list + '```\nWhen granting/denying permissions, use the first value, not the one in parentheses.'
		msg = await ctx.send(perm_list)
		await track(msg)

	@commands.has_permissions(administrator=True)
	@perms.command(name='listpresets')
	async def list_presets(self, ctx):
		''' Provides a list of permission quick-setup presets. '''
		embed = discord.Embed(title='\u2139 Preset list', description='The following default permission schemes are available. Select with ``{0}perms preset <name>``, and customize with ``{0}perms grant``, ``{0}perms deny``, and ``{0}perms clear``.'.format(self.bot.command_prefix), colour=discord.Colour(CONSTANTS.EMBED_COLOR_STANDARD))

		presets = None
		with open('data/default_presets.json') as preset_file:
			presets = json.load(preset_file)
		
		for preset in presets:
			embed.add_field(name=preset['name'], value=preset['description'])
			for role in preset['roles']:
				perms_string = 'With permissions: ```\n'
				for pname, pval in role['permissions'].items():
					perms_string = perms_string + 'Permission {0}: {1}\n'.format(pname, pval)
				perms_string = perms_string + '```'

				embed.add_field(name='\u2192Adds role: {0}'.format(role['name']), value=perms_string, inline=False)

		msg = await ctx.send(content='', embed=embed)
		await track(msg, ctx.author)


	@commands.has_permissions(administrator=True)
	@perms.command(name='preset')
	async def setup_preset(self, ctx, preset_name):
		''' (Admin-only) Sets up permissions based on a built-in preset.
		  ' WARNING: This will OVERWRITE any existing permissions.
		'''
		if not preset_name:
			raise commands.BadArgument('Please provide a preset name to use.')
		
		presets = None
		with open('data/default_presets.json') as preset_file:
			presets = json.load(preset_file)

		preset = None
		for possible_preset in presets:
			if possible_preset['name'].lower() == preset_name.lower():
				preset = possible_preset

		if not preset:
			raise commands.BadArgument('Preset {0} not found. Try `{1}perms list` for a list of presets.'.format(preset_name, self.bot.command_prefix))

		existing_perms = False
		with sql_cur(self.db) as cur:
			cur.execute('SELECT * FROM permissions WHERE guild_id=?;', (ctx.guild.id,))
			if cur.fetchone():
				existing_perms = True

		if existing_perms:
			embed = discord.Embed(title='\U0001f6a8 WARNING!', colour=discord.Colour(0xc7b61a), description='Hector already has permission records for this server! Continuing will erase these records and replace them with preset values!')
			embed.add_field(name='If you are sure,',value='Press the \u26a0 button.', inline=False)
			embed.set_footer(text='This command will time out in 60 seconds. To cancel, wait until time-out.')
			warn_msg = await ctx.send(content='',embed=embed) 
			await warn_msg.add_reaction('\u26a0')

			def check(reaction, user):
				return user == ctx.message.author and str(reaction.emoji) == '\u26a0' and reaction.message.id == warn_msg.id

			try:
				reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=check)

			except TimeoutError:
				await warn_msg.clear_reactions()
				await warn_msg.edit(content='Confirmation timed out.')
				await track(warn_msg, ctx.author)
				return

			else:
				await warn_msg.clear_reactions()
				await warn_msg.edit(content='Confirmed. Setting up permissions from preset {0}.'.format(preset['name']))
				with sql_cur(self.db) as cur:
					cur.execute('DELETE FROM permissions WHERE guild_id=?;', (ctx.guild.id,))
		for role in preset['roles']:
			perm_val = _construct_from_preset_string(role['permissions'])
			if role['name'] == '*':
				# Handle @everyone separately
				with sql_cur(self.db) as cur:
					cur.execute('INSERT INTO permissions (guild_id, role_id, permissions) VALUES (?,?,?);', (ctx.guild.id, ctx.guild.default_role.id, perm_val))
			else:
				if not 'color' in role.keys():
					role['color'] = CONSTANTS.EMBED_COLOR_STANDARD
				new_role = await ctx.guild.create_role(name=role['name'],colour=discord.Colour(role['color']),mentionable=True,reason='Setting up permissions from preset (requesting user: {0})'.format(ctx.message.author))
				with sql_cur(self.db) as cur:
					cur.execute('INSERT INTO permissions (guild_id, role_id, permissions) VALUES (?,?,?);', (ctx.guild.id, new_role.id, perm_val))
		await ctx.message.add_reaction('✅')
	
	@commands.command(name='myperms')
	async def my_perms(self, ctx, user:discord.Member=None):
		''' Check your own permissions or those of another user. '''
		global _perms_lut_unaliased
		if not user:
			user = ctx.message.author
		perms = await get_permissions(user, ctx.guild)

		embed = discord.Embed(title='Permissions for {0}:'.format(user), description='Calculated from {0}\'s roles.'.format(user.name), colour=discord.Colour(CONSTANTS.EMBED_COLOR_STANDARD))
		embed.set_thumbnail(url=user.avatar_url)
		embed.set_footer(text='Permission bytes: 0b{0:016b}.'.format(perms))

		if user.guild_permissions.administrator:
			embed.add_field(name='Guild Administrator',value='\u2705 Guild/server administrators bypass all permission checks. If {0} was not an administrator, their permissions would be as follows:'.format(user), inline=False)

		for key,val in _perms_lut_unaliased.items():
			if _denied(perms, val):
				embed.add_field(name=key,value='\u26d4 Denied!', inline=False)
			elif _has(perms, val):
				embed.add_field(name=key,value='\u2705 Granted!', inline=False)
			else:
				embed.add_field(name=key,value='\u274c Not granted.', inline=False)

		msg = await ctx.send(content='',embed=embed)
		await track(msg, ctx.author)
				


async def get_permissions(member, guild):
	tracked_roles = {}
	with sql_cur(sql_con()) as cur:
		cur.execute('SELECT role_id,permissions FROM permissions WHERE guild_id=?', (guild.id,))
		for role in cur.fetchall():
			tracked_roles[role[0]] = role[1]
	
	if len(tracked_roles) == 0:
		return 0

	permissions = 0
	
	for role in member.roles:
		if role.id in tracked_roles.keys():
			role_perms = tracked_roles[role.id]
			permissions = _perms_combine(role_perms, permissions)
	
	return permissions

async def has_permission(ctx, perm):
	if ctx.message.author.guild_permissions.administrator:
		return True # Override for guild admins.
	author = ctx.message.author
	perms = await get_permissions(ctx.message.author, ctx.guild)
	if not (_has(perms, perm) and not _denied(perms, perm)):
		raise commands.errors.MissingPermissions([_to_string(perm)])
	
	return True

def setup(bot):
	bot.add_cog(Permissions(bot))
