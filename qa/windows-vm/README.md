# Windows VM Validation

This bundle is for a real Windows-on-ARM regression run in a disposable VM.

It validates the public `easy-claudecode.app-win` release in three stages:

1. Windows VM boots to the installer/desktop.
2. The shared folder can see the repository copy.
3. An OEM hook installs Python, starts the backend, and checks:
   - `GET /claude-console/status`
   - `GET /claude-console/bootstrap`

## Host-side mount layout

Bind these host folders into a Dockur Windows ARM VM:

- `./storage:/storage`
- `./shared:/shared`
- `./oem:/oem`

The repository should be copied into `./shared/easy-claudecode.app-win`.

## OEM hook

The `oem/` folder contains:

- `install.bat`
- `validate-easy-claudecode.ps1`

Windows runs `C:\OEM\install.bat` during the first-boot automation stage.
The PowerShell validator writes a JSON result file back to the shared host folder:

- `\\host.lan\\Data\\vm-validation-result.json`

## Expected success shape

The result JSON should report:

- `pythonReady = true`
- `pipInstallOk = true`
- `backendStarted = true`
- `statusOk = true`
- `bootstrapOk = true`
- `ok = true`

## Notes

- This validation is intentionally backend-first. It does not require a live Claude CLI login.
- On hosts without KVM acceleration, the Windows installation can be significantly slower.
