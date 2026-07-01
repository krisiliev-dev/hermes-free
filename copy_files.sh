#!/usr/bin/env bash
# Copy the modified Hermes files into the user's Hermes installation.
# Usage: ./copy_files.sh [path-to-hermes-agent]
# If path is omitted, defaults to ~/.hermes/hermes-agent

HERMES_AGENT_DIR="${1:-$HOME/.hermes/hermes-agent}"
echo "Target Hermes agent directory: $HERMES_AGENT_DIR"

if [[ ! -d "$HERMES_AGENT_DIR" ]]; then
    echo "Error: Directory $HERMES_AGENT_DIR does not exist."
    echo "Please ensure Hermes is installed or provide the correct path."
    exit 1
fi

# Copy hermes_tools.py to the hermes-agent root
cp hermes_tools.py "$HERMES_AGENT_DIR/"
echo "Copied hermes_tools.py to $HERMES_AGENT_DIR"

# Copy updated agent_init.py
cp agent/agent_init.py "$HERMES_AGENT_DIR/agent/"
echo "Copied agent/agent_init.py to $HERMES_AGENT_DIR/agent/"

# Ensure the hermes-cli config module is present (for cfg_get/set)
# It's usually already there; we just ensure we have the latest.
cp -r hermes_cli "$HERMES_AGENT_DIR/../"
echo "Copied hermes_cli to $HERMES_AGENT_DIR/.."

echo "Done. Remember to restart Hermes for changes to take effect."
