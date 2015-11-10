#!/bin/bash

# Constants
GETTEXT_DOMAIN="syncthing-gtk"
MESSAGES_PO="messages.po"

for lang in locale/* ; do
	filename=${lang}/LC_MESSAGES/${GETTEXT_DOMAIN}.po
	mo=${lang}/LC_MESSAGES/${GETTEXT_DOMAIN}.mo
	msgfmt ${filename} -o ${mo}
	echo "Created" ${mo}
done
