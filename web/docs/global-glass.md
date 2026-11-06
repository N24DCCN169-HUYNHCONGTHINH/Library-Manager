# Shared glass appearance

`static/library/glass.css` loads last in the common base template so all regular Library Hub pages share the same surfaces, forms, tables and navigation. No business permissions or data are changed.

- Resting main surfaces: alpha 0.63, which is 25% less opacity than the previous login alpha 0.84. Light input alpha 0.57; dark input alpha 0.5625. Theme-specific text and borders remain legible.
- Fine-pointer hover: main panels return to alpha 0.84, lift 2px and scale 1.004; book cards lift 4px and scale 1.012. Buttons lift 2px and scale 1.025. Table rows stay in place and use a highlight. Form focus suppresses the outer panel transform.
- Menus and autocomplete lists use alpha 0.91 (0.97 on hover) for readable overlaps; their ancestor stacking contexts are raised while open.
- The Canada library photo is the fallback background. Existing personal wallpaper still overrides it. Attribution and license are visible in the common footer.
- Reduced-motion disables transforms/transitions. Reduced-transparency and browsers without backdrop-filter get solid surfaces. Printing removes the wallpaper and uses dark text on white. Hover motion is disabled on touch-only devices.
- For checking: home, catalogue, dashboard, circulation menus, reports/form tables, account/appearance forms, login and register, in light/dark, plus mobile layout. Preview data must not be presented as actual library statistics.

## Pinned navigation and opt-in movement

The topbar and left rail are fixed and have separate View Transition names. Header height is measured so content begins below it. Only same-origin navigation links inside these two bars opt into scene/content motion: vertical rail uses the Y axis, topbar uses X. Main content is the only sliding content snapshot; the bars remain stationary.

The decorative layer remains enlarged by 12% on each edge. Plain reloads, filter/search/pagination links, form submissions, browser Back and tabs inside the content do not move the image. In-place circulation changes use the same opt-in rule. Local sessionStorage keeps coordinates plus a short-lived numeric direction/axis timestamp; it stores no URLs or account data. Reduced-motion disables animation, printing hides navigation and the photo. Browsers without cross-document View Transitions use ordinary navigation.

All rail icon states explicitly define foreground/background contrast, including custom coloured icons, active circulation and bottom settings/logout controls.

Selected/hover/focus-visible menu items, tabs, suggestions and theme/view switches share explicit selection foreground/background pairs: dark green with near-white text in Dark mode; pale green with dark ink in Light mode. Child icons and captions inherit the selection foreground instead of keeping the old light-theme colours.
