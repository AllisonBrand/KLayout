#!/bin/bash

# Used to push only the production files to main branch from dev branch

# --- CONFIGURATION ---
MAIN_BRANCH="main"
DEV_BRANCH="dev"

# List production files relative to the repo root (space-separated)
PRODUCTION_FILES=(
    "README.md"
    ".gitignore"
    # SweepLib is the same as MyLib, but only loads a few example cases into the library, rather than everything in the dev branch
    "pymacros/SweepLib.lym" 
    "python/helpers/"
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

# 2. Track the starting branch so we can return to it later
START_BRANCH=$(git branch --show-current)
if [ "$START_BRANCH" != "$DEV_BRANCH" ] && [ "$START_BRANCH" != "$MAIN_BRANCH" ]; then
    echo "❌ Error: You must run this script from either '$DEV_BRANCH' or '$MAIN_BRANCH'."
    exit 1
fi

# 3. Block execution if there are uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: You have uncommitted changes on '$START_BRANCH'. Please stash or commit them first."
    exit 1
fi

echo "🚀 Starting selective publish process..."

# 4. Move to main branch to receive the updates
if [ "$START_BRANCH" != "$MAIN_BRANCH" ]; then
    echo "🔄 Switching to branch '$MAIN_BRANCH'..."
    git switch "$MAIN_BRANCH"
fi

# 5. Restore only the production files directly from the dev branch
echo "📦 Pulling clean production files from '$DEV_BRANCH'..."
git restore --source="$DEV_BRANCH" --staged --worktree -- "${PRODUCTION_FILES[@]}"
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to restore files from '$DEV_BRANCH'."
    echo "🔄 Returning you to '$START_BRANCH'..."
    git switch "$START_BRANCH"
    exit 1
fi

# 6. Commit and push the updates
echo "📝 Committing updates to '$MAIN_BRANCH'..."
git commit -m "$COMMIT_MSG"
echo "⬆️ Pushing to GitHub..."
git push origin "$MAIN_BRANCH"

# 7. Safely return the user to their original branch
if [ "$START_BRANCH" != "$MAIN_BRANCH" ]; then
    echo "🔄 Returning to your starting branch '$START_BRANCH'..."
    git switch "$START_BRANCH"
fi

echo "✅ Success! Production files are live on '$MAIN_BRANCH'."
