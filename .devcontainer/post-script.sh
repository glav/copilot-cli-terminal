#!/usr/bin/env bash

set -e
set -o pipefail

log() {
	printf "========== %s ==========%s" "$1" $'\n'
}

err() {
	printf "[ ERROR ]: %s%s" "$1" $'\n' >&2
	exit 1
}

install_uv() {
	if command -v uv &>/dev/null; then
		return 0
	fi

	if ! command -v curl &>/dev/null; then
		err "'curl' is required to install 'uv'"
	fi

	log "Installing uv"

	curl -LsSf "https://astral.sh/uv/install.sh" | sh

	# uv installs to ~/.local/bin by default
	export PATH="$HOME/.local/bin:$PATH"

	if ! command -v uv &>/dev/null; then
		err "'uv' installation completed but 'uv' is still not on PATH"
	fi

	uv --version
}

install_uv

echo ----------------------------------------------
echo If you want help using the prompt library or list
echo of available prompts, simply type:
echo 'What prompts are available to use?'
echo ----------------------------------------------
