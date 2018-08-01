
import discord
from discord.ext import commands
from discord import Member, Role

from sql.sql import sql_cur, sql_con
from messages import track

class Permissions:
	''' Manages user permissions '''
	def __init__(self, bot):
		self.bot = bot
		self.db = sql_con()
	
	@commands.has_permissions(administrator=True)
	@commands.group(name='chanop')
	async def chanop(self, ctx):
		''' (Admin-only) Administrator commands for managing chanops '''
		pass

	@chanop.command(name='setrole')
	async def set_role(self, ctx, role: Role):
		''' (Admin-only) - Sets the chanop role.
		  ' If promote is called before this command, Hector will
			' create a default role.
		'''
		if not role:
			raise discord.ext.commands.BadArgument(message="Role not found!")
		else:
			print('Setting admin role for guild ' + str(ctx.guild) + ' = ' + str(role))
			with sql_cur(self.db) as cur:
				cur.execute('DELETE FROM permissions WHERE guild_id=?;', (ctx.guild.id,))
				cur.execute('INSERT INTO permissions (admin_role_id, guild_id) VALUES (?,?);', (role.id, ctx.guild.id))
		await ctx.message.add_reaction('✅')
	

	@chanop.command(name='unsetrole')
	async def unset_role(self, ctx):
		''' (Admin-only) - Makes Hector stop considering a previously-set chanop role.
		  ' This will not remove the role; it will only remove the association
			' of that role with chanop status.
		'''
		print('Unsetting admin role for guild ' + str(ctx.guild))
		with sql_cur(self.db) as cur:
			cur.execute('DELETE FROM permissions WHERE guild_id=?;', (ctx.guild.id,))
		
		await ctx.message.add_reaction('✅')
		

	@chanop.command()
	async def promote(self, ctx, mention: Member):
		''' (Admin-only) - promotes a user to Hector chanop. '''
		if not mention:
			raise discord.ext.commands.BadArgument(message="User not found!")
		else:
			print('Promoting: ' + str(mention))
			note = None
			with sql_cur(self.db) as cur:
				cur.execute('SELECT admin_role_id FROM permissions WHERE guild_id=?', (ctx.guild.id,))
				row = cur.fetchone()
				if row:
					admin_role = discord.utils.get(ctx.guild.roles, id=row[0])
					if not admin_role:
						raise discord.ext.commands.CheckFailure(message='Chanop role is missing! Has it been deleted?')

					await mention.add_roles(admin_role, reason='Promoted by administrator {0}.'.format(ctx.message.author))
					await ctx.message.add_reaction('✅')
				else:
					admin_role = await ctx.guild.create_role(name='Hector Chanop', colour=discord.Colour(0x338888), mentionable=True, reason='Creating default chanop role.')
					cur.execute('INSERT INTO permissions (admin_role_id, guild_id) VALUES (?,?);', (admin_role.id, ctx.guild.id))
					await mention.add_roles(admin_role, reason='Promoted by administrator {0}.'.format(ctx.message.author))
					note = await ctx.send('Note: Created default chanop role.')
					await ctx.message.add_reaction('✅')
			if note:
				await track(note, ctx.message.author)

	
	@chanop.command()
	async def demote(self, ctx, mention: Member):
		''' (Admin-only) - demotes a user from Hector chanop status. '''
		if not mention:
			raise discord.ext.commands.BadArgument(message="User not found!")
		else:
			print('Demoting: ' + str(mention))
			with sql_cur(self.db) as cur:
				cur.execute('SELECT admin_role_id FROM permissions WHERE guild_id=?', (ctx.guild.id,))
				row = cur.fetchone()
				if row:
					admin_role = discord.utils.get(ctx.guild.roles, id=row[0])
					if not admin_role:
						raise discord.ext.commands.CheckFailure(message='Chanop role is missing! Has it been deleted?')

					if not admin_role in mention.roles:
						raise discord.ext.commands.BadArgument(message="User is not chanop. Cannot demote.")

					await mention.remove_roles(admin_role, reason='Demoted by administrator {0}.'.format(ctx.message.author))
					await ctx.message.add_reaction('✅')
				else:
					raise discord.ext.commands.BadArgument(message="No chanop role found.")
	
async def is_chanop(ctx):
	author = ctx.message.author
	chanop_role = None
	with sql_cur(sql_con()) as cur:
		cur.execute('SELECT admin_role_id FROM permissions WHERE guild_id=?', (ctx.guild.id,))
		row = cur.fetchone()
		if row:
			chanop_role = discord.utils.get(ctx.guild.roles, id=row[0])
			if not chanop_role:
				raise discord.ext.commands.CheckFailure(message='Chanop role is missing! Has it been deleted?')
		else:
			raise discord.ext.commands.CheckFailure(message='No chanop role! Promote a user or set a chanop role first!')
	return (chanop_role in author.roles)

async def check_chanop(ctx):
	ischanop = await is_chanop(ctx)
	if ischanop:
		return True
	else:
		raise discord.ext.commands.errors.MissingPermissions(['Channel Operator'])
		

def chanop_only():
	return commands.check(check_chanop)

def setup(bot):
	bot.add_cog(Permissions(bot))
