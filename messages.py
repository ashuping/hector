from sql.sql import sql_cur, sql_con

async def track(message, author=None):
	'''
	  ' Marks a message in the database so that it will be automatically
	  ' deleted if the sender or an admin reacts with the 'trash' emoji
	'''
	await message.add_reaction('🚮')
	sql_db = sql_con()
	aid = 0
	if author:
		aid = author.id
	with sql_cur(sql_db) as cur:
				cur.execute("INSERT INTO tracked_messages (messid, sender_uid, track_time) VALUES (?, ?, ?);", (message.id, aid, message.created_at))
