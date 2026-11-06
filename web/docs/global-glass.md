# Shared glass appearance

`static/library/glass.css` loads last in the common base template so all regular Library Hub pages share the same surfaces, forms, tables and navigation. No business permissions or data are changed.

- Resting main surfaces: alpha 0.63, which is 25% less opacity than the previous login alpha 0.84. Light input alpha 0.57; dark input alpha 0.5625. Theme-specific text and borders remain legible.
- Fine-pointer hover: main panels return to alpha 0.84, lift 2px and scale 1.004; book cards lift 4px and scale 1.012. Buttons lift 2px and scale 1.025. Table rows stay in place and use a highlight. Form focus suppresses the outer panel transform.
- Menus and autocomplete lists use alpha 0.91 (0.97 on hover) for readable overlaps; their ancestor stacking contexts are raised while open.
- The Canada library photo is the fallback background. Existing personal wallpaper still overrides it. Attribution and license are visible in the common footer.
- Reduced-motion disables transforms/transitions. Reduced-transparency and browsers without backdrop-filter get solid surfaces. Printing removes the wallpaper and uses dark text on white. Hover motion is disabled on touch-only devices.
- For checking: home, catalogue, dashboard, circulation menus, reports/form tables, account/appearance forms, login and register, in light/dark, plus mobile layout. Preview data must not be presented as actual library statistics.

## Route camera movement

`scene.js` runs before body paint. A fixed, decorative image layer extends 12% past every viewport edge (124% size), and translates by at most 5% of that layer between route-specific viewpoints. Each transition takes 1.8s, then stops; scrolling and pointer movement do not animate the background. Navigation inside circulation tabs also updates the viewpoint. Only two numeric coordinates are stored in sessionStorage; no URLs, queries, credentials or account data are stored. Reduced-motion disables image movement, print hides the layer, and without JavaScript the same enlarged photograph remains static.
