# Formula Campus Discuss RTC initialization fix

2026-11-18: browser RTC logs repeatedly reported `no transceiver available when updating direction` and recovery before media negotiation. Initialize the existing ordered audio/camera/screen slots synchronously during peer creation, before initial negotiationneeded and updateDownload. Respect enableStreaming=false, preserve current upload tracks and per-peer download direction, and reuse already present slots. Upstream mail source is not modified.

Install: `scripts/odoo-cli.sh -i campus_rtc_fix --without-demo=all`. Every call participant must hard-refresh the web client after deployment. Real two-device audio/video verification is required.
