#!/bin/bash
# Used to generate some icons
# Requires inkscape and imagemagick pacages

ICODIR=./icons/		# Directory with icons
SI_FRAMES=12 		# Number of animation frames for status icon

for size in 16 24 32 ; do
	# Rotating 'syncing' status icon is generated from multilayer svg
	inkscape ${ICODIR}/si-syncthing.svg --export-id-only \
		--export-area-page \
		--export-id=background \
		--export-png=/tmp/si-syncthing-back-${size}.png \
		--export-width=${size} --export-height=${size}
	
	# Generate default icon for each rotation
	for i in $(seq 0 $((SI_FRAMES-1))) ; do
		echo si-syncthing-${i}.png
		inkscape ${ICODIR}/si-syncthing.svg --export-id-only \
			--export-area-page \
			--export-id=rot${i} \
			--export-png=/tmp/si-syncthing-${size}-${i}.png \
			--export-width=${size} --export-height=${size}
		
		convert \
			/tmp/si-syncthing-back-${size}.png \
			/tmp/si-syncthing-${size}-${i}.png \
			-gravity center -compose over -composite \
			${ICODIR}/${size}x${size}/status/si-syncthing-${i}.png
		
	done
	
	# Generate icon for idle state and grayscale icon for unknown/offline state
	echo si-syncthing-idle.png
	convert \
			/tmp/si-syncthing-back-${size}.png \
			/tmp/si-syncthing-${size}-0.png \
			-gravity center -compose over -composite \
			${ICODIR}/${size}x${size}/status/si-syncthing-idle.png	
	echo si-syncthing-unknown.png
	convert \
			/tmp/si-syncthing-back-${size}.png \
			/tmp/si-syncthing-${size}-0.png \
			-gravity center -compose over -composite \
			-colorspace Gray \
			${ICODIR}/${size}x${size}/status/si-syncthing-unknown.png

	# Generate black & white icons
	for cols in "background-black rot black" "background-white rotblack white" ; do
		cols=($cols)
		inkscape ${ICODIR}/si-syncthing.svg --export-id-only \
			--export-area-page \
			--export-id=${cols[0]} \
			--export-png=/tmp/si-syncthing-back-${size}.png \
			--export-width=${size} --export-height=${size}
		
		# Generate icon for each rotation
		for i in $(seq 0 $((SI_FRAMES-1))) ; do
			echo si-syncthing-${cols[2]}-${i}.png
			inkscape ${ICODIR}/si-syncthing.svg --export-id-only \
				--export-area-page \
				--export-id=${cols[1]}${i} \
				--export-png=/tmp/si-syncthing-${size}-${i}.png \
				--export-width=${size} --export-height=${size}
			
			convert \
				/tmp/si-syncthing-back-${size}.png \
				/tmp/si-syncthing-${size}-${i}.png \
				-gravity center -compose over -composite \
				${ICODIR}/${size}x${size}/status/si-syncthing-${cols[2]}-${i}.png
		done
		
		# Generate icon for idle state and grayscale icon for unknown/offline state
		echo si-syncthing-${cols[2]}-idle.png
		convert \
				/tmp/si-syncthing-back-${size}.png \
				/tmp/si-syncthing-${size}-0.png \
				-gravity center -compose over -composite \
				${ICODIR}/${size}x${size}/status/si-syncthing-${cols[2]}-idle.png
		
		echo si-syncthing-${cols[2]}-unknown.png
		inkscape ${ICODIR}/si-syncthing.svg --export-id-only \
			--export-area-page \
			--export-id=${cols[1]}-unknown \
			--export-png=/tmp/si-syncthing-${size}-unknown.png \
			--export-width=${size} --export-height=${size}
		
		convert \
				/tmp/si-syncthing-back-${size}.png \
				/tmp/si-syncthing-${size}-unknown.png \
				-gravity center -compose over -composite \
				-colorspace Gray \
				${ICODIR}/${size}x${size}/status/si-syncthing-${cols[2]}-unknown.png
	done
done