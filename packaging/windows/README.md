# Windows x64 package

Build the downloadable zip from a Linux or macOS checkout that has Node, npm, and `x86_64-w64-mingw32-gcc`:

```bash
python3 packaging/windows/build_windows_zip.py
```

The zip is written to `packaging/windows/dist/NorfrontClaw-windows-x64.zip`. That file and the staged `node_modules` stay out of git. Upload the zip as a GitHub Release asset.

`start.exe` is at the top of the zip. It puts portable Python and portable Node on `PATH` and runs `python -m norfront_claw.boot`. The console packages are installed for Windows x64 while the zip is built, so the first double-click does not run `npm install` and does not need Git, winget, or an already-open terminal.

First double-click prints a sentence before each slow step: checking the machine, downloading the brain, the browser package, asking for a key, opening the page. A missing DeepSeek key is a hidden prompt after that sentence. If the brain download fails or takes more than a few seconds, one sentence says so and the console still opens. Chrome is not bundled. Missing hardware KVM or a TypeSafe key is a sentence on the page. The window stays open.

A second double-click, while that window is still open, does not install anything and does not start a second console. It opens the page again.
