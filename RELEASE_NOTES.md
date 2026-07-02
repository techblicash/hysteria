# ProxyGUI v1.0.0-beta

Windows x64 portable beta release.

## Highlights

- PySide6 desktop GUI for proxy node management.
- sing-box core support with generated configuration.
- Mihomo and Xray core binaries bundled for future adapter support.
- Multi-subscription groups.
- Clash YAML and sing-box JSON import.
- Import preview, de-duplication, selected-node import.
- TCP and URL latency tests.
- Batch latency tests, batch edit, cleanup, export, backup and restore.
- System tray, quick node switching, autostart and auto-connect last node.
- Global, rule and direct routing modes for sing-box.
- Portable PyInstaller one-folder build.

## Package

Use the generated folder directly:

```text
dist/ProxyGUI/ProxyGUI.exe
```

Or distribute the generated zip:

```text
release/ProxyGUI-v1.0.0-beta-windows-x64.zip
```

## Known Limitations

- Auto-update checks only prompt; they do not download or replace the application yet.
- Mihomo and Xray adapters are placeholders, although the core binaries are bundled.
- The release is not code-signed, so Windows may show an unknown publisher warning.
