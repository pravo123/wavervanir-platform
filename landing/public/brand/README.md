# Brand assets

Place the WaverVanir logo at:

```
landing/public/brand/wavervanir-logo.png
```

Required attributes (per operator brief, 2026-05-25):

- Do **not** recreate, alter, crop, recolor, or stylize the logo in this slice.
- The HTML / React components reference exactly that path.
- Alt text: `WaverVanir — Process Over Prediction`.
- Dark backgrounds: black (`#000`) is used in nav and hero so the gold + blue marks read cleanly.

The binary file is not committed by the assistant in this slice — the operator should drop the
provided PNG at the path above before pushing or previewing.

Verification:

```bash
test -f landing/public/brand/wavervanir-logo.png && echo OK
```
