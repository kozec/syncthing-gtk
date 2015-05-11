#!/bin/bash
# Used to generate some icons
# Requires inkscape and imagemagick pacages

ICODIR=./icons/		# Directory with icons
SI_FRAMES=12 		# Number of animation frames for status icon

for size in 16 24 32 ; do
	# Rotating 'syncing' status icon is generated from multilayer svg
	inkscape ${ICODIR}/si-syncing.svg --export-id-only \
		--export-area-page \
		--export-id=background \
		--export-png=/tmp/si-syncing-back-${size}.png \
		--export-width=${size} --export-height=${size}
	
	# Generate icon for each rotation
	for i in $(seq 0 $((SI_FRAMES-1))) ; do
		echo si-syncing-${i}.png
		inkscape ${ICODIR}/si-syncing.svg --export-id-only \
			--export-area-page \
			--export-id=rot${i} \
			--export-png=/tmp/si-syncing-${size}-${i}.png \
			--export-width=${size} --export-height=${size}
		
		convert \
			/tmp/si-syncing-back-${size}.png \
			/tmp/si-syncing-${size}-${i}.png \
			-gravity center -compose over -composite \
			${ICODIR}/${size}x${size}/apps/si-syncing-${i}.png
		
	done
	
	# Generate icon for idle state and grayscale icon for unknown/offline state
	echo si-idle.png
	convert \
			/tmp/si-syncing-back-${size}.png \
			/tmp/si-syncing-${size}-0.png \
			-gravity center -compose over -composite \
			${ICODIR}/${size}x${size}/apps/si-idle.png	
	echo si-unknown.png
	convert \
			/tmp/si-syncing-back-${size}.png \
			/tmp/si-syncing-${size}-0.png \
			-gravity center -compose over -composite \
			-colorspace Gray \
			${ICODIR}/${size}x${size}/apps/si-unknown.png
done
