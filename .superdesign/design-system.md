# YAFA VANAM Design System

## Product context

YAFA VANAM is a premium botanical beauty storefront for makeup, skincare, fragrance and personalized shade guidance. Authentication should feel like part of the shopping ritual: calm, trustworthy, editorial and easy on mobile. Key account flows are registration, six-digit email confirmation, sign-in, password reset and access to orders, saved products and beauty profiles.

## Visual foundation

- Use a warm ivory page background (`#fcf9fa`) and white surfaces (`#ffffff`).
- Use near-black (`#111111` / `#2c2c2c`) for primary text and CTAs.
- Use rose (`#c94c6b` or `#c96e85`) for focus, active states and restrained accents.
- Use muted brown-gray (`#66615e`, `#6f6a63`) for supporting copy and `rgba(23,21,18,.16)` for borders.
- Error surfaces use `#fbeeed`, a `#c0392b` left rule and `#8f2f25` text.
- Display headings use Georgia or Times New Roman serif with tight tracking. Interface labels and controls use Arial/system sans-serif.
- Avoid gradients except the existing extremely subtle rose radial wash. Do not introduce purple, neon, blue brand treatments or unrelated fonts.

## Form components

- Minimum control height: 48px; mobile tap targets at least 44px.
- Modal fields use 10px radii; dedicated auth-page fields may remain more editorial/square if consistent with the page.
- Focus uses a rose border with a soft 3px rose ring and visible keyboard outline.
- Primary CTA is near-black with white uppercase or strong label text.
- Inline validation is plain-language and placed directly under the affected field.
- The birthday control should make day, month and year independently understandable, support keyboard input, and provide a smooth bounded year list rather than forcing long native-calendar navigation.
- Birthday output must remain strict `YYYY-MM-DD` for Cognito while the visible UI follows the visitor's locale.
- Gender remains inclusive: Female, Male, Non-binary, Prefer not to say.

## Authentication layout

- Dedicated page: centered editorial card/sheet within the storefront shell, readable on 360px mobile through desktop.
- Modal: max width 540px, 22px radius, 31–52px responsive padding, blurred dark backdrop, quiet leaf ornament.
- Verification state: prominent six-digit code input, clear error/notice area, primary Verify action, resend cooldown and a back-to-sign-in path.
- Keep the YAFA VANAM ritual eyebrow and calm editorial headline hierarchy.

## Motion and accessibility

- Use 150–260ms ease transitions for focus, hover, dropdown opening and selection.
- The year list should use smooth scrolling, scroll snapping or equivalent controlled focus, and automatically center the selected/current year.
- Respect `prefers-reduced-motion`; disable smooth animation when requested.
- Preserve visible labels, semantic form controls, one-time-code autocomplete, keyboard navigation and screen-reader status/error announcements.
- Never rely on color alone for state.

## Responsive behavior

- Below 520px, controls and dropdown panels must fit within the viewport with no horizontal overflow.
- Birthday segments may stack only on very narrow screens; otherwise use an efficient three-part row.
- Dropdown/popover height should be bounded so year selection never takes over the full page.
