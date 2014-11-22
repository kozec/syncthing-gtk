#!/bin/bash
# Used to generate some icons

ICODIR=./icons/		# Directory with icons
SI_FRAMES=12 		# Number of animation frames for status icon

# Rotating 'syncing' status icon is generated from multilayer svg
inkscape ${ICODIR}/si-syncing.svg --export-id-only \
	--export-area-page \
	--export-id=background \
	--export-png=/tmp/si-syncing-back.png \
	--export-width=22 --export-height=22

for i in $(seq 0 $((SI_FRAMES-1))) ; do
	echo si-syncing-${i}.png
	inkscape ${ICODIR}/si-syncing.svg --export-id-only \
		--export-area-page \
		--export-id=rot${i} \
		--export-png=/tmp/si-syncing-${i}.png \
		--export-width=22 --export-height=22
	
	convert \
		/tmp/si-syncing-back.png \
		/tmp/si-syncing-${i}.png \
		-gravity center -compose over -composite \
		${ICODIR}/si-syncing-${i}.png
	
done

# --export-area-drawing
