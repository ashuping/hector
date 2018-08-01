import sqlite3
import json

class database_initialize_error(BaseException):
	'''
	  ' Raised when the database can't be initialized properly
	'''

class sql_cur:
	'''
	  ' Cursor object for sqlite3 database.
		' Manages automatic creation/committing of data.
		' 
		' To use:
		' 
		'   with sql_cur(sql_con) as cursor:
		'     do_things_with(cursor)
		' 
		'   do_other_things() # Cursor object is closed and committed before
		'                       this line - use cursor.rollback() to roll
		'                       back changes
	'''
	def __init__(self, connection):
		self.con = connection
	
	def __enter__(self):
		self.cur = self.con.raw.cursor()
		return self.cur
	
	def __exit__(self, xtype, xvalue, xtraceback):
		self.con.raw.commit()
		self.cur.close()

class sql_con:
	def __init__(self):
		self.table_prefix = ''
		self.raw = sqlite3.connect('data/sqlite3.db')
		with open('sql/schema.json') as schema_file:
			self.schema = json.load(schema_file)

		table_status = self.table_check()
		if table_status == 0:
			return
		elif table_status == 1:
			print('Database is empty. Initializing...')
			self.setup_tables(force=False)
		elif table_status == 2:
			print('Some tables are missing. Creating missing tables...')
			self.setup_tables(force=False)
		else:
			print('Database does not match expected schema! Re-initialize?')
			reinit = input('[y/n]:')
			if reinit.lower() == 'y':
				print('Deleting all data and re-initializing...')
				self.setup_tables(force=True)
			else:
				print('Table setup cannot continue. Aborting.')
				raise database_initialize_error()
	
	def table_check(self, schema=None, table_prefix=None):
		'''
		  ' Verify the table structure in the database
			' 
			' Parameters:
			'   schema = dict from schema.json, detailing the expected
			'            table schema for the database.
			' 
			'   table_prefix = if present, prepend this to table names as
			'                  specified in the schema.
			' 
			' Returns:
			'   0 if everything is normal
			'   1 if the database is empty
			'   2 if some tables are present but others are absent
			'   3 if tables do not follow the expected schema
		'''
		if not schema:
			schema = self.schema
		if not table_prefix:
			table_prefix = self.table_prefix
			
		all_tables_present = True
		database_empty = True
		schema_ok = True

		with sql_cur(self) as cur:
			cur.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
			res_raw = cur.fetchall()

		res_fixed = []
		for result in res_raw:
			res_fixed.append(result[0])

		for table in schema:
			tname = table_prefix + table['name']
			if tname in res_fixed:
				database_empty = False
				with sql_cur(self) as cur:
					cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='{0}'".format(tname))
					res_raw = cur.fetchall()
					res_preproc = res_raw[0][0][res_raw[0][0].find('(')+1:res_raw[0][0].find(')')].split(',')
					res = []
					for column in res_preproc:
						column = column.strip()
						column_processed = [column[:column.find(' ')], column[column.find(' ')+1:].split(' ')[0]]
						res.append(column_processed)
				
				if len(res) != len(table['schema']):
					schema_ok = False # missing column(s)

				for column in res:
					match = False
					for col_descriptor in table['schema']:
						if col_descriptor['name'] == column[0]:
							if col_descriptor['type'].lower() == column[1].lower():
								match = True
								break
							else:
								print('type mismatch on column: ' + str(column))
								schema_ok = False # Type mismatch

					if not match:
						print('unexpected column: ' + str(column))
						print('dump: ' + str(res_raw) + ' -> ' + str(res))
						schema_ok = False # Unexpected column

			else:
				all_tables_present = False # missing table

		if not schema_ok:
			return 3
		elif database_empty:
			return 1
		elif not all_tables_present:
			return 2
		else:
			return 0

	def setup_tables(self, force=False):
		'''
		  ' Sets up the proper tables in the sqlite3 database
			' 
			' Parameters:
			'   force = whether to delete all tables and re-initialize. This
			'           option is DANGEROUS, and should not be used unless
			'           necessary
		'''

		if force: # delete all present tables
			with sql_cur(self) as cur:
				cur.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
				table_list_unfixed = cur.fetchall()

				for table in table_list_unfixed:
					tname = table[0]
					cmd = 'DROP TABLE ' + tname + ';'
					print(str('Removing table ' + tname))
					cur.execute(cmd)

		with sql_cur(self) as cur:
			cur.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
			table_list_unfixed = cur.fetchall()

			table_list = []

			for table in table_list_unfixed:
				table_list.append(table[0])
				print(str(table[0]))

			for table in self.schema:
				tname = self.table_prefix + table['name']
				if tname in table_list:
					continue # ignore tables which already exist
				else:
					cmd = 'CREATE TABLE ' + tname + ' ('
					for index, column in enumerate(table['schema']):
						if index != 0:
							cmd = cmd + ', '
						cmd = cmd + column['name'] + ' ' + column['type']
						if 'primary' in column: # columns with primary:true are PRIMARY KEY columns
							if column['primary']:
								cmd = cmd + ' PRIMARY KEY'
					
					cmd = cmd + ');'
					print(str('Creating table ' + tname + ' with command ' + cmd))
					cur.execute(cmd) # create table
