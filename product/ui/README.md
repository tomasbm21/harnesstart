# Norfront Claw operator console

Local Vite + React + Tailwind + shadcn/ui page. It is a dense stand-in for `./product/claw` on this Linux checkout: doctor, key presence, VM backend, brain, and Jev observe / guards / choose / browse.

Keys render as `set` or `missing`. The page does not read secret values and does not call DeepSeek or TypeSafe.

## Run

From the repo root:

```bash
cd product/ui
npm install
npm run dev
```

Open the URL Vite prints (default http://127.0.0.1:5173).

`npm run build` typechecks and writes `dist/`.

## Status snapshot

`public/status.json` is a checked-in fixture. To refresh presence from this machine:

```bash
python3 product/ui/write_status.py
```

That writes gitignored `public/status.local.json`. The page loads the local file when it exists, otherwise the fixture. The writer refuses to emit anything except `set` / `missing` for keys, and exits if a secret value would land in the JSON.

## shadcn components

accordion, alert, alert-dialog, aspect-ratio, avatar, badge, breadcrumb, button, card, checkbox, collapsible, command, dialog, dropdown-menu, hover-card, input, input-group, label, popover, progress, radio-group, scroll-area, select, separator, sheet, skeleton, slider, sonner, switch, table, tabs, textarea, toggle, toggle-group, tooltip
