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
    "python/helpers/*"
    "python/Wrapper.py"
    "python/Sweep.py"
    "python/testing/HEMT.py"
    "python/testing/CircularHEMT.py"
)
# ---------------------

# Capture and validate the commit message argument
$COMMIT_MSG = $args[0]
if ([string]::IsNullOrEmpty($COMMIT_MSG)) {
    Write-Error "Error: Please provide a commit message as an argument."
    Write-Host "Usage: .\publish.ps1 `"Your commit message here`"" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting selective publish process..." -ForegroundColor Cyan

# Create a unique path for the hidden background folder
$TEMP_DIR = Join-Path $env:TEMP "klayout_main_worktree_$(Get-Random)"

# Extract the 'main' branch into that hidden folder
Write-Host "Creating hidden temporary worktree..." -ForegroundColor Cyan
git worktree add $TEMP_DIR $MAIN_BRANCH
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error: Failed to create temporary worktree." -Category InvalidOperation
    exit 1
}

try{
    # Jump context into the hidden worktree folder to commit and push
    Push-Location $TEMP_DIR

    # Pull only the production files directly from the dev branch
    Write-Host "Pulling clean production files from '$DEV_BRANCH'..." -ForegroundColor Cyan
    git restore --source=$DEV_BRANCH --staged --worktree -- $PRODUCTION_FILES
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Error: Failed to restore files from '$DEV_BRANCH'."
        exit 1
    }

    # Track all changes explicitly in the temporary index
    git add .

    # Display what is about to be committed
    Write-Host "`n=== STAGED CHANGES FOR PRODUCTION ===" -ForegroundColor Yellow
    git status
    Write-Host "=====================================`n" -ForegroundColor Yellow

    # Interactive confirmation prompt
    $CHOICE = Read-Host "Do you want to proceed the commit and push to '$MAIN_BRANCH'? [y/n]"
    if ($CHOICE.Trim().ToLower() -ne 'y') {
        Write-Host "Publish aborted by user. Cleaning up..." -ForegroundColor Yellow
        exit 0
    }

    # Commit and push the updates.
    Write-Host "Committing updates to '$MAIN_BRANCH'..." -ForegroundColor Cyan
    git commit -m $COMMIT_MSG

    Write-Host "️ Pushing to GitHub..." -ForegroundColor Cyan
    git push origin $MAIN_BRANCH

} finally {

    # Return to your normal project folder safely
    Pop-Location

    # Clean up and completely remove the hidden worktree metadata and folder
    Write-Host "Cleaning up temporary workspace..." -ForegroundColor Cyan
    # Delete the temporary worktree
    git worktree remove --force $TEMP_DIR 
    # Delete the temporary directory
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Recurse -Force $TEMP_DIR
    }

}

Write-Host "Success! Production files are live on '$MAIN_BRANCH' via background push." -ForegroundColor Green