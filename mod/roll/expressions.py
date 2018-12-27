''' Parses mathematical expressions with die rolls '''

import math
import random

KEYWORDS = ['+', '-', '*', '/', '(', ')', '[[', ']]', '$']
ESCAPE_CHAR = '\\'  # Literal \


class ExpressionSyntaxError(Exception):
	''' Thrown when an expression has invalid syntax '''
	pass


class ExpressionVariableError(Exception):
	''' Thrown when an expression uses an invalid variable '''
	pass


class Expression:
	''' Parses a mathematical expression, including a die roll '''

	def __init__(self, stringExpression=None):
		self.op = None # The base operation to be run
		if stringExpression:
			self.compile(stringExpression)
	
	def isop(self):
		return False

	def compile(self, stringExpression):
		''' Parses a string into an operation list, to be run later. '''
		global KEYWORDS
		self.op = None
		tmpExpression = []
		pieces = break_over(stringExpression, KEYWORDS)

		toPass = 0
		for dex, piece in enumerate(pieces):
			if toPass > 0:
				toPass = toPass - 1
				continue
			
			if piece == '(':
				offs = 1
				indent = 1
				asm = ''
				while(True):
					if dex + offs >= len(pieces):
						raise ExpressionSyntaxError('In expression "' \
							+ stringExpression + '": Mismatched parentheses!')
					if pieces[dex+offs] == ')':
						indent = indent - 1
						if indent == 0:
							tmpExpression.append(Expression(asm))
							toPass = offs
							break

						asm = asm + pieces[dex+offs]
						offs = offs + 1
					elif pieces[dex+offs] == '(':
						indent = indent + 1
						asm = asm + pieces[dex+offs]
						offs = offs + 1
					else:
						asm = asm + pieces[dex+offs]
						offs = offs + 1

			elif piece == '[[':
				offs = 1
				indent = 1
				asm = ''
				while(True):
					if dex + offs >= len(pieces):
						raise ExpressionSyntaxError('In expression "' \
							+ stringExpression + '": Mismatched double-brackets!')

					if pieces[dex+offs] == ']]':
						indent = indent - 1
						if indent == 0:
							tmpExpression.append(DieExpression(asm))
							toPass = offs
							break
						else:
							asm = asm + pieces[dex+offs]
						offs = offs + 1
					elif pieces[dex+offs] == '[[':
						indent = indent + 1
						asm = asm + pieces[dex+offs]
						offs = offs + 1
					else:
						asm = asm + pieces[dex+offs]
						offs = offs + 1

			elif piece == '$':
				if dex == len(pieces)-1:
					raise ExpressionSyntaxError('In expression "' \
						+ stringExpression + '": Unexpected $ at end of input!')
				tmpExpression.append(VarExpression(piece + pieces[dex+1]))
				toPass = 1

			elif piece in '+-*/':
				if dex == 0 or dex == len(pieces)-1:
					raise ExpressionSyntaxError('In expression "' \
						+ stringExpression + '": Misplaced + operator')
				if pieces[dex-1] in '+-':                    # Attempt to infer the
					tmpExpression.append(ConstExpression('0')) # meaning of multiple
				elif pieces[dex-1] in '*/':                  # consecutive operators
					tmpExpression.append(ConstExpression('1')) # i.e. '+ - 2' becomes 
				tmpExpression.append(piece)                  # '+ 0 - 2'

			else:
				tmpExpression.append(ConstExpression(piece))
		
		if len(tmpExpression) == 1:
			self.op = tmpExpression[0]
		else:
			# In-place simplification
			ops = tmpExpression
			dex = 0
			lpass = 0 # 0 = multiplication/division, 1 = addition/subtraction
			while True:
				if dex >= len(ops):
					if lpass == 0:
						lpass = 1
						dex = 0
					else:
						break

				if not isinstance(ops[dex],str):
					dex = dex + 1
					continue

				if ops[dex] in '*/' and lpass == 0:
					if ops[dex] == '*':
						ops[dex-1] = MultOperator(ops[dex-1],ops[dex+1])
					else:
						ops[dex-1] = DivOperator(ops[dex-1],ops[dex+1])
					del(ops[dex])
					del(ops[dex])
				elif ops[dex] in '+-' and lpass == 1:
					if ops[dex] == '+':
						ops[dex-1] = PlusOperator(ops[dex-1],ops[dex+1])
					else:
						ops[dex-1] = MinusOperator(ops[dex-1],ops[dex+1])
					del(ops[dex])
					del(ops[dex])
				else:
					dex = dex + 1
			
			if len(ops) > 1:
				raise ExpressionSyntaxError('In expression "' \
					+ stringExpression + '": More than one expression!')

			self.op = ops[0]
				
	
	def run(self, vvars=None):
		return self.op.run(vvars)

class DieExpression:
	''' Parses a die-roll expression '''

	def __init__(self, stringExpression):
		self.lhs = None
		self.rhs = None
		self.compile(stringExpression)
	
	def isop(self):
		return False

	def compile(self, stringExpression):
		pieces = break_over(stringExpression, ['[[',']]','d'])
		depth = 0
		dpos = -1
		dex = 0
		for piece in pieces:
			if piece == '[[':
				depth = depth + 1
				dex = dex + 2
			elif piece == ']]':
				depth = depth - 1
				dex = dex + 2
			elif piece == 'd':
				if depth == 0:
					dpos = dex
					break
				else:
					dex = dex + 1
			else:
				dex = dex + len(piece)

		if dpos == -1:
			lside = stringExpression
			rside = '1'
		else:
			lside = stringExpression[:dpos]
			rside = stringExpression[dpos+1:]
		if rside == '':
			raise ExpressionSyntaxError('In die expression "' \
				+ stringExpression + '": Die expression must have a right-hand side!')
		if lside == '':
			lside = '1'
		self.lhs = Expression(lside)
		self.rhs = Expression(rside)
	
	def run(self, vvals):
		lval = self.lhs.run(vvals)  # First, run any sub-expressions so that
		rval = self.rhs.run(vvals)  # we have numbers for lval and rval

		if rval == 1:
			return lval

		lval = math.floor(lval)  # Truncate any decimal expressions
		rval = math.floor(rval)  # unless the rval is 1.
		i = 0
		for dex in range(lval):  # Then, roll each die individually and sum
			i = i + random.randrange(rval) + 1

		return i
		
class ConstExpression:
	''' Parses a constant-number expression '''

	def __init__(self, stringExpression):
		self.val = 0
		self.compile(stringExpression)
	
	def isop(self):
		return False
	
	def compile(self, stringExpression):
		try:
			self.val = float(stringExpression)
		except ValueError:
			raise ExpressionSyntaxError('In constant expression "' \
				+ stringExpression + '": Not a constant!')
	
	def run(self, vvals):
		return self.val

class VarExpression:
	''' Parses a variable '''

	def __init__(self, stringExpression):
		self.var = None
		self.compile(stringExpression)
	
	def isop(self):
		return False
	
	def compile(self, stringExpression):
		''' Note: This function discards anything passed except the first
		    variable.
		'''
		vloc = find_ignore_escaped(stringExpression, '$')
		if vloc == -1 or vloc == len(stringExpression)-1:
			raise ExpressionSyntaxError('In variable expression "' \
				+ stringExpression + '": Not a variable!')

		vex = stringExpression[vloc+1:]
		eloc = find_first_not_of(vex,'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')[0]
		if eloc != -1:
			vex = vex[:eloc]

		if len(vex) == 0:
			raise ExpressionSyntaxError('In variable expression "' \
				+ stringExpression + '": Invalid variable name (names must contain only letters)!')

		self.var = Variable(vex)

	def run(self, vvars):
		if not vvars:
			raise ExpressionVariableError('Variable ' + self.var.getAliases()[0] \
				+ ' has no value!')

		for name, value in vvars.items():
			if self.var.isIdentifiedBy(name):
				return value

		raise ExpressionVariableError('Variable ' + self.var.getAliases()[0] \
			+ ' has no value!')

class Variable:
	''' Holds a variable number '''
	
	def __init__(self, identifier):
		self.aliases = []
		self.aliases.append(identifier)
	
	def alias(self, alias):
		self.aliases.append(alias)
	
	def isIdentifiedBy(self, alias):
		return alias in self.aliases
	
	def getAliases(self):
		return self.aliases
	
	def equals(self, other):
		otherAliases = other.getAliases()
		for alias in self.aliases:
			if alias in otherAliases:
				return True

		return False
	
class ArithOperator:
	''' Represents an arithmetic operator '''
	def __init__(self, left, right):
		self.left = left
		self.right = right
	
	def isop(self):
		return True

class PlusOperator(ArithOperator):
	''' Represents the addition operator '''
	def __init__(self, left, right):
		super().__init__(left, right)

	def run(self, vvars):
		return self.left.run(vvars) + self.right.run(vvars)

class MinusOperator(ArithOperator):
	''' Represents the subtraction operator '''
	def __init__(self, left, right):
		super().__init__(left, right)
	
	def run(self, vvars):
		return self.left.run(vvars) - self.right.run(vvars)

class MultOperator(ArithOperator):
	''' Represents the multiplication operator '''
	def __init__(self, left, right):
		super().__init__(left, right)

	def run(self, vvars):
		return self.left.run(vvars) * self.right.run(vvars)

class DivOperator(ArithOperator):
	''' Represents the division operator '''
	def __init__(self, left, right):
		super().__init__(left, right)

	def run(self, vvars):
		return self.left.run(vvars) / self.right.run(vvars)


def break_over(source, keywordList):
	''' Breaks a single string (source) into a list of strings, separated
	    by the keywords in keywordList.

			Example: with the default KEYWORDS and s='(4+5er342)*6',
			break_over(s, KEYWORDS) returns 
			['(','4','+','5er342',')','*','6']
	'''
	pieces = []
	dex = 0
	while True:
		inst = find_first_of(source, keywordList, dex)
		pos = inst[0]
		kword = inst[1]
		if pos == -1:
			piece = source[dex:]
			if len(piece) > 0:
				pieces.append(piece)
			return pieces
		else:
			piece = source[dex:pos]
			ender = source[pos:pos+len(kword)]
			if(len(piece) > 0):
				pieces.append(piece)
			pieces.append(ender)
				
			dex = pos + len(kword)

def find_first_of(source, keywordList, dex=0):
	''' Finds the first instance of any of the keywords in keywordList in
	    source, excepting escaped keywords (that is, keywords preceded by
			ESCAPE_CHAR, default value \), beginning at dex

			Returns the list [index, keyword], where index is the index of the
			first instance of keyword
	'''
	first = None
	for keyword in keywordList:
		pos = find_ignore_escaped(source, keyword, dex)
		if pos != -1:
			if not first or pos < first[0]:
				first = [pos, keyword]
	
	if first:
		return first
	else:
		return [-1,None]

def find_first_not_of(source, allowed, dex=0):
	''' Finds the first character NOT present in allowed in source

			Returns the list [index, c], where index is the index of the
			first instance of invalid character c

			Or [-1,None] if there are no non-allowed characters in source
	'''
	for d, c in enumerate(source):
		if d >= dex and c not in allowed:
			return [dex,c]
	
	return [-1,None]

def find_ignore_escaped(source, expr, dex=0, escapeChar=None):
	''' Finds the first instance of the sequence expr in source, starting
	    at dex, excepting sequences that begin with escapeChar (default is
			a single backslash.

			Example: if s='Big, poin\ty teeth' (where the \ is a literal
			backslash, i.e. \\) and x = 't', then	find_ignore_escaped(s,e) 
			returns 13 (the index of the first 't' not preceded by a \)
	''' 
	global ESCAPE_CHAR
	if not escapeChar or len(escapeChar) > 1:
		escapeChar = ESCAPE_CHAR
	
	while True:
		pos = source.find(expr,dex)
		if pos == -1:
			return -1
		elif pos == 0:
			return 0
		elif source[pos-len(escapeChar):pos] == escapeChar:
			dex = pos+1 #ignore escaped expression
		else:
			return pos
