# Written by Gemini

# Run with:
# publish.bat "Your commit message"


# --- CONFIGURATION ---
$MAIN_BRANCH = "main"
$DEV_BRANCH = "dev"

# List production files relative to the repo root (comma-separated strings)
$PRODUCTION_FILES = @(
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
$COMMIT_MSG = $args[0]
if ([string]::IsNullOrEmpty($COMMIT_MSG)) {
    Write-Error "Error: Please provide a commit message as an argument."
    Write-Host "Usage: .\publish.ps1 `"Your commit message here`"" -ForegroundColor Yellow
    exit 1
}

# 2. Track the starting branch so we can return to it later
$START_BRANCH = (git branch --show-current).Trim()
if ($START_BRANCH -ne $DEV_BRANCH -and $START_BRANCH -ne $MAIN_BRANCH) {
    Write-Error "Error: You must run this script from either '$DEV_BRANCH' or '$MAIN_BRANCH'."
    exit 1
}

# 3. Block execution if there are uncommitted changes
$STATUS = git status --porcelain
if (![string]::IsNullOrEmpty($STATUS)) {
    Write-Error "Error: You have uncommitted changes on '$START_BRANCH'. Please stash or commit them first."
    exit 1
}

Write-Host "Starting selective publish process..." -ForegroundColor Cyan

# 4. Create a unique path for the hidden background folder
$TEMP_DIR = Join-Path $env:TEMP "klayout_main_worktree_$(Get-Random)"

# 5. Extract the 'main' branch into that hidden folder
Write-Host "Creating hidden temporary worktree..." -ForegroundColor Cyan
git worktree add $TEMP_DIR $MAIN_BRANCH
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error: Failed to create temporary worktree." -Category InvalidOperation
    exit 1
}

try {
    # 6. For each production file, copy it from your working dir to the hidden dir
    Write-Host "Syncing production files to background folder..." -ForegroundColor Cyan
    foreach ($FILE_PATH in $PRODUCTION_FILES) { # $FILE_PATH is relative to the repo root

        $SOURCE_PATH = Resolve-Path $FILE_PATH
        $TARGET_PATH = Join-Path $TEMP_DIR $FILE_PATH 
        
        # Ensure the destination directories exist inside the worktree in $TEMP_DIR
        $TARGET_PARENT = Split-Path $TARGET_PATH -Parent # Strips the filename from the path
        # If the parent directory doesn't exist, create it
        if (!(Test-Path $TARGET_PARENT)) {
            New-Item -ItemType Directory -Path $TARGET_PARENT -Force | Out-Null
        }
        
        # Copy the physical file to the hidden directory
        Copy-Item -Path $SOURCE_PATH -Destination $TARGET_PATH -Force
    }

    # 7. Jump context into the hidden worktree folder to commit and push
    Push-Location $TEMP_DIR
    
    Write-Host "Committing updates to '$MAIN_BRANCH'..." -ForegroundColor Cyan
    git add .
    git commit -m $COMMIT_MSG
    
    Write-Host "️ Pushing to GitHub..." -ForegroundColor Cyan
    git push origin $MAIN_BRANCH
    
    # Return to your normal project folder safely
    Pop-Location
}
finally {
    # 8. Clean up and completely remove the hidden worktree metadata and folder
    Write-Host "Cleaning up background workspace..." -ForegroundColor Cyan
    # Delete the temporary worktree
    git worktree remove --force $TEMP_DIR 
    # Delete the temporary directory
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Recurse -Force $TEMP_DIR
    }
}

Write-Host "Success! Production files are live on '$MAIN_BRANCH' via background push." -ForegroundColor Green

# # 4. Move to main branch to receive the updates
# if ($START_BRANCH -ne $MAIN_BRANCH) {
#     Write-Host "Switching to branch '$MAIN_BRANCH'..." -ForegroundColor Cyan
#     git switch $MAIN_BRANCH
# }

# # 5. Restore only the production files directly from the dev branch
# Write-Host "Pulling clean production files from '$DEV_BRANCH'..." -ForegroundColor Cyan
# git restore --source=$DEV_BRANCH --staged --worktree -- $PRODUCTION_FILES
# if ($LASTEXITCODE -ne 0) {
#     Write-Error "Error: Failed to restore files from '$DEV_BRANCH'."
#     Write-Host "Returning you to '$START_BRANCH'..." -ForegroundColor Yellow
#     git switch $START_BRANCH
#     exit 1
# }

# # 6. Commit and push the updates
# Write-Host "Committing updates to '$MAIN_BRANCH'..." -ForegroundColor Cyan
# git commit -m $COMMIT_MSG
# Write-Host "️ Pushing to GitHub..." -ForegroundColor Cyan
# git push origin $MAIN_BRANCH

# # 7. Safely return the user to their original branch
# if ($START_BRANCH -ne $MAIN_BRANCH) {
#     Write-Host "Returning to your starting branch '$START_BRANCH'..." -ForegroundColor Cyan
#     git switch $START_BRANCH
# }

# Write-Host "Success! Production files are live on '$MAIN_BRANCH'." -ForegroundColor Green
