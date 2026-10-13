param(
    [Parameter(Mandatory=$true)]
    [string]$IpAddress,
    
    [string]$Username = "raspscreen",
    [string]$Password = "raspscreen#1234"
)

$plink = "C:\Program Files\PuTTY\plink.exe"
$pscp = "C:\Program Files\PuTTY\pscp.exe"
$localDir = "c:\Franck\Projets\Antigravity\RaspEcran"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Déploiement automatique RaspEcran vers $IpAddress    " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan

$hostKey = "SHA256:6BVqRSxYkR39iYwa+RqCIQt5yCokahIWNB/Oo1pOeFU"

# 1. Test de connectivité SSH
Write-Host "[1/4] Test de connexion SSH..." -ForegroundColor Yellow
$testOutput = & $plink -ssh -batch -hostkey $hostKey -pw $Password "$Username@$IpAddress" "echo 'SSH_CONNECT_OK'" 2>&1
if ($testOutput -notmatch "SSH_CONNECT_OK") {
    Write-Host "Erreur de connexion SSH : $testOutput" -ForegroundColor Red
    exit 1
}
Write-Host "Connexion SSH réussie !" -ForegroundColor Green

# 2. Préparation du dossier et copie des fichiers via pscp
Write-Host "[2/4] Préparation et transfert des fichiers du projet vers le Raspberry Pi..." -ForegroundColor Yellow
& $plink -ssh -batch -hostkey $hostKey -pw $Password "$Username@$IpAddress" "mkdir -p /home/$Username/RaspEcran"
& $pscp -batch -hostkey $hostKey -r -pw $Password "$localDir\*" "$Username@$IpAddress`:/home/$Username/RaspEcran/"
Write-Host "Transfert terminé !" -ForegroundColor Green

# 3. Exécution de l'installation
Write-Host "[3/4] Exécution de l'installateur (services, écran 800x480, kiosque, protection SD/eMMC)..." -ForegroundColor Yellow
$installCmd = "chmod +x /home/$Username/RaspEcran/install.sh && echo '$Password' | sudo -S bash /home/$Username/RaspEcran/install.sh"
& $plink -ssh -batch -hostkey $hostKey -pw $Password "$Username@$IpAddress" $installCmd

# 4. Redémarrage pour finalisation
Write-Host "[4/4] Redémarrage du Raspberry Pi pour activer le kiosque..." -ForegroundColor Yellow
& $plink -ssh -batch -hostkey $hostKey -pw $Password "$Username@$IpAddress" "echo '$Password' | sudo -S reboot"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Déploiement terminé ! Le Pi redémarre sur le Kiosque." -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
