# Define the resource groups
$resourceGroups = @(
    "AZ-CORE-PROD-01-ESNS-PROD-EASTUS-RG-01",
    "AZ-CORE-PROD-01-ESAT-PROD-WESTUS-RG-01",
    "AZ-ENTAPP-PROD-01-CLDS-PROD-WESTUS-RG-01",
    "AZ-CORE-PROD-01-ITKA-PROD-EASTUS-RG-01",
    "AZ-CORE-PROD-01-ESAA-PROD-WESTUS-RG-01"
)

# Log file
$logFile = "scope_lock_log.txt"

# Function to log actions
function Log-Action {
    param (
        [string]$message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "$timestamp - $message"
    Add-Content -Path $logFile -Value $logEntry
}

# Prompt user for action
$action = Read-Host "Do you want to 'delete' or 'restore' scope locks? Enter 'delete' or 'restore'"

if ($action -eq 'delete') {
    # Remove locks
    foreach ($rg in $resourceGroups) {
        $lockName = "$rg-lock"
        try {
            Remove-AzResourceLock -LockName $lockName -ResourceGroupName $rg -Force
            Log-Action "Removed lock $lockName from resource group $rg"
        } catch {
            Log-Action "Failed to remove lock $lockName from resource group $rg: $(${_.Exception.Message})"
        }
    }
    Log-Action "Scope locks deletion completed"
} elseif ($action -eq 'restore') {
    # Restore locks
    foreach ($rg in $resourceGroups) {
        $lockName = "$rg-lock"
        try {
            New-AzResourceLock -LockName $lockName -LockLevel CanNotDelete -ResourceGroupName $rg
            Log-Action "Restored lock $lockName to resource group $rg"
        } catch {
            Log-Action "Failed to restore lock $lockName to resource group $rg: $(${_.Exception.Message})"
        }
    }
    Log-Action "Scope locks restoration completed"
} else {
    Write-Host "Invalid action. Please run the script again and enter 'delete' or 'restore'."
    Log-Action "Invalid action entered by user"
}

Log-Action "Script completed successfully"