#!/bin/bash

# UNFINISHED!! Would be for Linux/Unix systems.
# Windows is supported via publish.ps1

# Used to push only the production files to main branch from dev branch

# --- CONFIGURATION ---
MAIN_BRANCH="main"
DEV_BRANCH="dev"

# List production files relative to the repo root (comma-separated strings)
$PRODUCTION_FILES = (
    "README.md"
    ".gitignore"
    ".gitattributes"
    # SweepLib is the same as MyLib, but only loads a few example cases into the library, rather than everything in the dev branch
    "pymacros/SweepLib.lym" 
    "python/helpers/*"
    "python/Wrapper.py"
    "python/Sweep.py"
    "python/testing/HEMT.py"
    "python/testing/CircularHEMT.py"
)
# ---------------------

# 1. Capture and validate the commit message argument
COMMIT_MSG="$1"
if [ -z "$COMMIT_MSG" ]; then
    echo "❌ Error: Please provide a commit message as an argument."
    echo "Usage: ./publish_tool.sh \"Your commit message here\""
    exit 1
fi


# UNFINISHED!! 



echo "✅ Success! Production files are live on '$MAIN_BRANCH'."
