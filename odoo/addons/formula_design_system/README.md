# Formula Design System (`formula_design_system`)

Design tokens, surgical backend restyling and a light/dark theme toggle for
Odoo 18 Community. Depends only on `web`. No external JS or CSS frameworks and
no web fonts loaded from external hosts.

## Theme toggle

- A moon/sun button sits in the systray (top navbar, next to the chat/activity icons).
- Odoo 18 CE serves `web.assets_web_dark` instead of `web.assets_web` when the
  `color_scheme` cookie is `dark` (`web/views/webclient_templates.xml`).
- The toggle writes `color_scheme=light|dark` (path `/`, one year) and reloads the page.
- Scope: the choice is stored per browser, not in the user record. Odoo 18 CE has no
  server-side color scheme preference. A per-user server field would need a
  `res.users` field plus a controller, which this addon does not add.

## Token names

All tokens are CSS custom properties on `:root`. Light values are in
`static/src/scss/fds_tokens.scss`; dark overrides in `fds_tokens.dark.scss`.
Consume them with a fallback, for example `var(--fds-primary, #635BFF)`.

| Group | Tokens |
| --- | --- |
| Surfaces | `--fds-bg`, `--fds-bg-muted`, `--fds-surface`, `--fds-surface-raised`, `--fds-border`, `--fds-border-strong` |
| Text | `--fds-text`, `--fds-text-muted` |
| Navigation | `--fds-navbar-bg`, `--fds-navbar-text` |
| Primary | `--fds-primary`, `--fds-primary-hover`, `--fds-primary-active`, `--fds-primary-text`, `--fds-primary-soft` |
| Success | `--fds-success`, `--fds-success-fill`, `--fds-success-text`, `--fds-success-soft` |
| Warning | `--fds-warning`, `--fds-warning-text`, `--fds-warning-soft` |
| Danger | `--fds-danger`, `--fds-danger-fill`, `--fds-danger-hover`, `--fds-danger-active`, `--fds-danger-text`, `--fds-danger-soft` |
| Focus | `--fds-focus` |
| Radius | `--fds-radius-sm` (6px), `--fds-radius-md` (10px), `--fds-radius-lg` (12px), `--fds-radius-pill` |
| Spacing | `--fds-space-1` (4px), `--fds-space-2` (8px), `--fds-space-3` (12px), `--fds-space-4` (16px), `--fds-space-6` (24px), `--fds-space-8` (32px) |
| Elevation | `--fds-shadow-card`, `--fds-shadow-hover`, `--fds-shadow-overlay` |
| Motion | `--fds-duration-fast` (150ms), `--fds-duration-base` (200ms), `--fds-duration-slow` (250ms), `--fds-ease` |
| Typography | `--fds-font-family` |

Contrast notes: the brand values `#EF4444`, `#0D9488` and `#F59E0B` are used for
icons, borders and accents. Text on buttons and badges uses the `-fill` or `-text`
variants (for example `--fds-danger-fill` #DC2626 with white text, 4.8:1) so that
WCAG AA (4.5:1 for normal text) holds.

## Restyled Odoo elements

Every selector is scoped under `body.o_web_client`:

- Top navbar (`.o_main_navbar`): background and entry color.
- Buttons: `.btn-primary`, `.btn-secondary`, `.btn-outline-primary`, `.btn-danger`
  with hover, active, disabled and `:focus-visible` states. `.btn.fds-icon-btn` is
  a 36px icon-only button.
- Form sheet (`.o_form_sheet_bg > .o_form_sheet`): radius and card shadow.
- List header (`.o_list_table > thead > tr > th`).
- Kanban cards (`.o_kanban_record`): radius, shadow, hover shadow.
- Badges (`.badge`): pill shape. Semantic modifiers `fds-badge--success`,
  `fds-badge--warning`, `fds-badge--danger`, `fds-badge--primary`.
- Dialogs (`.o_dialog .modal-content`) and notifications (`.o_notification`): radius.

## Accessibility and motion

- Keyboard focus: `:focus-visible` outline using `--fds-focus` inside `.o_web_client`.
- `prefers-reduced-motion: reduce` removes the transitions this addon adds.

## Tests

`tests/test_design_system.py` (tags `post_install`, `-at_install`,
`formula_design_system`) checks that the light and dark token files and the
toggle assets are registered in the right bundles, and that `web.assets_web_dark`
compiles without SCSS errors.

## Not included (scope of this slice)

- Breadcrumbs and sidebar changes (Phase 1 UI-02).
- Skeleton loaders, tooltips and confirmation dialogs (UI-04, UI-05).
- Compact density mode and per-user preference storage.
- Overriding Bootstrap SCSS variables (`web._assets_primary_variables`). Odoo's own
  primary color stays unchanged outside the selectors listed above.
- Visual regression screenshots and HOOT JavaScript tests (not run).
