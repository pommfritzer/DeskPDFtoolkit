# Windows 11 context menu

`OpenCommand.cpp` is an x64 native IExplorerCommand implementation. It supplies the app title and executable icon, hides itself for non-PDF selections, and forwards selected paths to the existing single-window app. The sparse MSIX manifest registers a packaged COM surrogate and a `.pdf` modern-context-menu verb. This does not change the system context-menu preference.

Build with Visual C++ x64 tools and the Windows SDK:

```powershell
./scripts/build-shell.ps1 -SigningThumbprint YOUR_CERTIFICATE_THUMBPRINT
```

The certificate must be a code-signing certificate with subject `CN=PDFtoolkit26` in the current user's personal certificate store. The build script never creates or trusts certificates. For a local development certificate, Windows package deployment may require an administrator-approved import of its public certificate into Local Machine Trusted People. Obtain explicit user consent for that trust change. Do not distribute private keys or automatically change trust stores.

Without a signing thumbprint, the script produces an explicitly unsigned package for preparation only; Windows will not register it for executable activations. Public distribution needs a suitable trusted production signing setup. CI builds without signing configuration retain the classic Explorer entry.

To include a signed modern-menu package in the installer, set `PDFTOOLKIT26_SHELL_CERT_THUMBPRINT` before running `scripts/build.ps1`. Native DLL filenames include the application version so upgrades do not overwrite a shell library still loaded by an older surrogate. The sparse identity has a separate version generated from the app version.

The installer registers the signed package for the installing user when Explorer integration is selected. Uninstall removes the package before deleting its files. The signing certificate is not removed automatically. `register.ps1` and `unregister.ps1` support manual repair/removal. Registry-based legacy commands remain available as fallback.

`VerifyCommand.cpp` is a small native verification program. It activates the registered packaged COM command, checks title and PDF-enabled state, and optionally invokes it for a supplied PDF path.

After registration, close and reopen the context menu. If Explorer has cached its old extension list, restart File Explorer or sign out and back in. A full PC reboot is normally unnecessary. See [Microsoft's packaged Explorer integration documentation](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/integrate-packaged-app-with-file-explorer).
