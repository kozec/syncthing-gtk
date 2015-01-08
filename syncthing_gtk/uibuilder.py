#!/usr/bin/env python2
"""
Syncthing-GTK - tools

Wrapper around GTKBuilder. Allows using conditional (<IF>) tags in
glade files.

Usage:
	- Crete instance
	- Enable conditions (enable_condition call)
	- Call add_from_file or add_from_string method
	- Continue as usual
"""

from __future__ import unicode_literals
from gi.repository import Gtk
from xml.dom import minidom
import logging
log = logging.getLogger("UIBuilder")

class UIBuilder(Gtk.Builder):
	def __init__(self):
		Gtk.Builder.__init__(self)
		self.conditions = set([])
		self.xml = None
	
	def add_from_file(self, filename):
		""" Builds UI from file """
		log.debug("Loading glade file %s", filename)
		self.add_from_string(file(filename, "r").read())
	
	def add_from_string(self, string):
		""" Builds UI from string """
		self.xml = minidom.parseString(string)
		self._build()
	
	def add_from_resource(self, *a):
		raise RuntimeError("add_from_resource is not supported")
	
	def enable_condition(self, *conds):
		""" Enables condition. Conditions are case-insensitive """
		for c in conds:
			log.debug("Enabled: %s", c)
			self.conditions.add(c)
	
	def disable_condition(self, *conds):
		""" Disables condition. Conditions are case-insensitive """
		for c in conds:
			log.debug("Disabled: %s", c)
			self.conditions.remove(c)
	
	def condition_met(self, cond):
		"""
		Returns True if condition is met. Empty condition is True.
		Spaces at begining or end of expressions are stripped.
		
		Supports simple |, & and !
		operators, but no parenthesis.
		(I just hope I'd never have to use them)
		"""
		if "|" in cond:
			for sub in cond.split("|", 1):
				if self.condition_met(sub):
					return True
			return False
		if "&" in cond:
			for sub in cond.split("&", 1):
				if not self.condition_met(sub):
					return False
			return True
		if cond.strip().startswith("!"):
			return not self.condition_met(cond.strip()[1:])
		return cond.strip() in self.conditions
	
	def _build(self):
		"""
		Fun part starts here. Recursively walks through entire XML DOM
		and removes all <IF> tags, replacing them with child nodes if when
		condition is met
		"""
		log.debug("Enabled conditions: %s", self.conditions)
		self._find_conditions(self.xml.documentElement)
		# Now this will convert parsed DOM tree back to XML and fed it
		# to Gtk.Builder XML parser.
		# God probably kills kitten every time when method is called...
		Gtk.Builder.add_from_string(self, self.xml.toxml("utf-8"))
	
	def _find_conditions(self, node):
		""" Recursive part for _build """
		for child in node.childNodes:
			if child.nodeType == child.ELEMENT_NODE:
				self._find_conditions(child)
				if child.tagName.lower() == "if":
					self._solve_if_element(child)
				elif child.getAttribute("if") != "":
					condition = child.getAttribute("if")
					if not self.condition_met(condition):
						log.debug("Removed '%s' by attribute: %s", child.tagName, condition)
						node.removeChild(child)
	
	def _solve_if_element(self, element):
		"""
		Reads "condition" attribute and decides if condition is met
		Conditions are case-insensitive
		"""
		condition = element.getAttribute("condition").lower().strip()
		if self.condition_met(condition):
			# Merge child nodes in place of this IF element
			# Remove ELSE elements, if any
			log.debug("Allowed node %s", condition)
			for elseem in getElementsByTagNameCI(element, "else"):
				element.removeChild(elseem)
			merge_with_parent(element, element)
		else:
			# Remove this element, but merge ELSE elemnets, if any
			log.debug("Removed node %s", condition)
			for elseem in getElementsByTagNameCI(element, "else"):
				merge_with_parent(elseem, element)
			element.parentNode.removeChild(element)

def getElementsByTagNameCI(node, tagname):
	"""
	Returns all elements with matching tag; Compares in
	case-insensitive way.
	"""
	tagname = tagname.lower()
	return [ child for child in node.childNodes if 
			(child.nodeType == child.ELEMENT_NODE and
			child.tagName.lower() == tagname)
		]

def merge_with_parent(element, insert_before):
	""" Merges child nodes with parent node """
	for child in element.childNodes:
		if child.nodeType == child.ELEMENT_NODE:
			element.removeChild(child)
			insert_before.parentNode.appendChild(child)
			insert_before.parentNode.insertBefore(child, insert_before)
	element.parentNode.removeChild(element)
