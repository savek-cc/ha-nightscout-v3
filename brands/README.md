# Brand assets for home-assistant/brands

Staging directory for a future PR against
<https://github.com/home-assistant/brands>.

Layout matches what `home-assistant/brands` expects under
`custom_integrations/<domain>/`:

| File             | Size    | Source                     | Shown on     |
| ---------------- | ------- | -------------------------- | ------------ |
| `icon.png`       | 256×256 | `nightscout-v3-light.png`  | Light theme  |
| `icon@2x.png`    | 512×512 | `nightscout-v3-light.png`  | Light theme (hi-DPI) |
| `dark_icon.png`  | 256×256 | `nightscout-v3.png`        | Dark theme   |
| `dark_icon@2x.png` | 512×512 | `nightscout-v3.png`     | Dark theme (hi-DPI) |

All four are 8-bit sRGB PNG with alpha channel.

## Submit

Once ready, fork <https://github.com/home-assistant/brands> and copy the
`custom_integrations/nightscout_v3/` directory across, then open a PR
per <https://github.com/home-assistant/brands/blob/master/README.md>.
HACS and the HA frontend pick up icons from that repository by domain
name, so nothing in the integration itself needs to reference them.
