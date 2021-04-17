import re, os, logging
log = logging.getLogger("stignoreparser")

def load_repo_ignore_regex(repo_path):
	"""
	Loads .stignore file from repo directory
	"""
	log.debug("Read repo and load .stignore if existing in " + repo_path)
	patterns = read_ignore_file(os.path.join(repo_path, '.stignore'))
	return convert_ignore_patterns_to_regex(patterns)

def convert_ignore_patterns_to_regex(patterns):
	"""
	Convert .stignore patterns to regex patterns
	"""
	regexes = []
	for pattern in patterns:
		parsed_pattern = parse_ignore_pattern(pattern)
		if not parsed_pattern == None:
			regexes.append(parsed_pattern)
	return regexes

def read_ignore_file(filepath):
	"""
	Reads pattern from .stignore file (reads also #include content)
	"""	
	patterns = []
	if not os.path.isfile(filepath):
		return patterns
	pathonly, filename = os.path.split(filepath)
	with open(filepath, "r") as f:
		for line in f.readlines():
			line = line.strip(" \r\t\n")
			if line.startswith("#include"):
				includepath = os.path.join(pathonly, line[9:])
				patterns.extend(read_ignore_file(includepath))
			elif not line.startswith("//") and line != "":
				patterns.append(line)
	return patterns

def parse_ignore_pattern(line):
	"""
	Reads pattern from .stignore file (reads also #include content)
	"""
	if line.startswith("//"):
		return None
	isExclude = False
	isCaseInsensitive = False
	isDeletable = False
	while True:
		if line.startswith("!") and not isExclude:
			isExclude = True
			line = line[1:]
		elif line.startswith("(?i)") and not isCaseInsensitive:
			isCaseInsensitive = True
			line = line[4:]
		elif line.startswith("(?d)") and not isDeletable:
			isDeletable = True
			line = line[4:]
		else:
			break
	flags = re.UNICODE
	if isCaseInsensitive:
		line = line.lower()
		flags = flags | re.IGNORECASE
	line = re.escape(line)
	if line.startswith("\/"):
		line = line
	elif line.startswith("\*\*\/"):
		line = '.*?/' + line[3:]
	else:
		line = '.*?/' + line
	line = line.replace('\*\*', '.*?').replace('\*','[^/]*?').replace('\?','[^/]').replace('\[', '[').replace('\]', ']')
	line = line + '$'
	excludeParents = []
	if isExclude:
		# Split pattern by path sep to find parent folder matches
		pathParts = line.split("\/")
		pathPart = ""
		for pathFolder in pathParts:
			if not pathFolder == "":
				pathPart = pathPart + "\/" + pathFolder + "$"
				excludeParents.append(re.compile(pathPart, flags))
	compiled_regex = { 'compiled': re.compile(line, flags), 'exclude': isExclude, 'excludeParents': excludeParents }
	return compiled_regex
