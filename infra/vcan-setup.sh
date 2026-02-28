#!/usr/bin/env bash
# vcan-setup.sh — Virtual CAN interface setup for Linux environments.
#
# Creates a vcan0 virtual CAN interface for live CAN frame injection.
# This is an alternative to candump replay mode and requires Linux
# with kernel module support (not available on macOS/Docker Desktop).
#
# Usage:
#   sudo ./vcan-setup.sh
#
# Prerequisites:
#   - Linux kernel with vcan module support
#   - Root/sudo privileges
#   - iproute2 package installed

set -euo pipefail

INTERFACE="vcan0"

echo "Setting up virtual CAN interface: ${INTERFACE}"

# Load vcan kernel module
if ! lsmod | grep -q "^vcan"; then
    echo "Loading vcan kernel module..."
    modprobe vcan
else
    echo "vcan module already loaded."
fi

# Create interface if it doesn't exist
if ip link show "${INTERFACE}" &>/dev/null; then
    echo "Interface ${INTERFACE} already exists."
else
    echo "Creating ${INTERFACE}..."
    ip link add dev "${INTERFACE}" type vcan
fi

# Bring interface up
ip link set up "${INTERFACE}"

echo "Virtual CAN interface ${INTERFACE} is up and ready."
echo ""
echo "Verify with: ip link show ${INTERFACE}"
echo "Monitor with: candump ${INTERFACE}"
