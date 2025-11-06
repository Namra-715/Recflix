#!/bin/bash
# Simple setup script for Recflix Database Query Tool

echo "=========================================="
echo "Recflix Database Query Tool Setup"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Check if pip is available
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ pip is not available. Please install pip first."
    exit 1
fi

echo "✓ pip is available"
echo ""

# Make the script executable
chmod +x database_query.py

echo "✓ Made database_query.py executable"
echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "You can now run the script with:"
echo "  python3 database_query.py"
echo ""
echo "The script will automatically install any missing dependencies."
echo ""

