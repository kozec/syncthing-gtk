#!/c/Python27/python.exe
"""
Update Chocolatey package from GitHub releases informations.

Requirements:
- Being on Windows
- Having Chocolatey installed (https://chocolatey.org/)
- Having warmup and nuget.commandline installed ("cinst warmup nuget.commandline")
- Having the API key configured ("nuget SetApiKey [API_KEY_HERE] -source http://chocolatey.org/" "https://chocolatey.org/account")
- Being a maintainer of the syncthing-gtk package on Chocolatey
"""


from __future__ import unicode_literals, print_function

import re, os, json
try:
       from urllib import request # Py3
except ImportError:
       import urllib2 as request  # Py2
       from io import open

print("Retrieving last version...")

releasesString = request.urlopen("https://api.github.com/repos/syncthing/syncthing-gtk/releases").read().decode('utf-8')
releases = json.loads(releasesString)

lastRelease = releases[0] # Improve if needed
version = ''
url = ''
releaseNotes = ''

version = lastRelease['name'].replace('v', '', )
releaseNotes = lastRelease['body'].replace('\r', '').replace(':\n-', ':\n\n-')

for asset in lastRelease['assets']:
	if re.match(r'.+win32-installer.exe', asset['name']):
		# url = "https://cdn.rawgit.com/syncthing/syncthing-gtk/releases/download/"+lastRelease['name']+"/"+asset['name']
		url = asset['browser_download_url']
assert(url != ''), "ERR No fitting script found"


print("Found version", version)

print("Updating files...")

nuspecFile = open("syncthing-gtk.nuspec", "r", encoding="utf8")
nuspecString = nuspecFile.read()
nuspecFile.close()

nuspecString = re.sub(r'<version>.*</version>', '<version>'+version+'</version>', nuspecString)
nuspecString = re.sub(r'<releaseNotes>[\w\W]*</releaseNotes>', '<releaseNotes>'+releaseNotes+'</releaseNotes>', nuspecString)

nuspecFile = open("syncthing-gtk.nuspec", "w", encoding="utf8")
print(nuspecString, file=nuspecFile, end="")
nuspecFile.close()

chocolateyInstallFile = open("tools/chocolateyInstall.ps1", "r", encoding="utf8")
chocolateyInstallString = chocolateyInstallFile.read()
chocolateyInstallFile.close()

chocolateyInstallString = re.sub(r'\$url ?= ?\'.*\'\n', '$url = \''+url+'\'\n', chocolateyInstallString)

chocolateyInstallFile = open("tools/chocolateyInstall.ps1", "w", encoding="utf8")
print(chocolateyInstallString, file=chocolateyInstallFile, end="")
chocolateyInstallFile.close()

print("Packaging...")

os.system("cpack")

input("Done! Press [Enter] to push or ^C to cancel pushing")

print("Pushing...")

os.system("cpush syncthing-gtk."+version+".nupkg")

print("Done!")
