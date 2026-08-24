# YAFA VANAM — Design System

## Design intent

YAFA VANAM is a **quiet-luxury beauty guide**: warm, intimate, botanical and assured. It must feel like a thoughtful beauty consultation, not a cosmetics marketplace shouting for attention. The experience pairs editorial calm with practical clarity so that skincare, shade matching, and checkout all feel easy to trust.

This system distils reusable principles studied across the `awesome-design-md` collection: one disciplined accent, meaningful surface contrast, generous whitespace, restrained type weights, product-first imagery, and components that repeat a single coherent visual grammar. It is original to YAFA VANAM; do not reproduce another brand's palette, typeface, logo, layout, copy, or distinctive visual signature.

## The visual voice

- **Warm, not sugary.** Use a paper-toned base and a deep charcoal ink. Pink appears as a refined rose signal, never as a candy wash.
- **Editorial, not ornamental.** A serif headline brings beauty and humanity; the UI remains crisp, quiet, and highly readable.
- **Botanical, not literal.** Suggest nature with soft leaf silhouettes, ingredient photography, and low-contrast tonal texture. Avoid clip-art leaves, generic spa gradients, and decorative clutter.
- **Guided, not clinical.** Recommendations and analysis should feel confident but friendly. Explanations are concise, scannable, and never overclaim.
- **Premium through restraint.** Let spacing, photography, typographic hierarchy, and a small number of deliberate accents do the work. Avoid excessive shadows, pill overload, and multiple competing CTA colours.

## Foundations

### Colour roles

| Role | Token / value | Use |
| --- | --- | --- |
| Ink | `--ink` / `#111111` | Primary text, strong outlines, primary actions |
| Paper | `--paper` / `#fcf9fa` | Main page canvas |
| Warm paper | `--warm-paper` / `#f5e8ec` | Gentle panels, hover surfaces, product-stage backgrounds |
| Blush | `--peach` / `#f3e4e7` | Supporting surface only; never a primary CTA |
| Signature rose | `#c94c6b` | Progress, selected states, primary brand moments, key CTA surfaces |
| Deep rose | `--copper` / `#985b6a` | Secondary brand detail and muted emphasis |
| Muted text | `--muted` / `#66615e` | Descriptions and secondary metadata |
| Rule | `--line` / `rgba(23, 21, 18, .16)` | Hairlines, field boundaries, quiet separation |
| Night canvas | `#0d0d0d` | Immersive advisor, results, and secure checkout journeys |
| Night text | `#f5e8eb` | Text on the night canvas |

Rules:

- A screen gets **one primary action colour**. On light surfaces use ink or signature rose; on night surfaces use signature rose.
- Use colour to show state and hierarchy, never merely to fill empty space.
- Keep error, success, and warning colours semantic and distinct from the signature rose.
- Preserve accessible contrast. Body text must remain clearly legible on every blush, photographic, and dark surface.

### Typography

Use the existing system deliberately:

- **Display:** `Georgia, "Times New Roman", serif`, weight 400. Large, close-set, calm. Use for page titles, key editorial moments, and product-story headings.
- **UI and body:** `Arial, Helvetica, sans-serif`, weight 400–700. Use for controls, advice, prices, labels, and functional content.
- **Eyebrow / metadata:** compact sans, 10–11px, weight 700, 0.14–0.16em tracking, uppercase only for short labels.

Type rules:

- Make display headings spacious through surrounding whitespace, not excessive weight.
- Keep paragraphs at a comfortable 1.5–1.6 line height and limit their measure to roughly 45–65 characters where possible.
- Avoid more than three active sizes inside one card. Product price and recommendation confidence are supporting information, not competing headlines.
- Do not use italic, bold, all caps, and colour simultaneously for emphasis.

### Spacing and shape

- Use a 4px base rhythm: 4, 8, 12, 16, 24, 32, 48, 64, 80.
- Give editorial bands 64–96px of vertical air on desktop; reduce deliberately on mobile rather than compressing every gap.
- Preserve the existing 44px minimum touch target. Primary actions should usually be 48–52px high.
- Use **modest rounding**: 2–3px for structured checkout, 10px for inputs and intimate overlays, 18–24px only for feature cards and imagery. Reserve fully rounded pills for a clear action or compact tag—not every component.
- Elevation comes first from surface contrast and hairlines. Shadows, if used, are soft and rare.

## Component grammar

### Buttons and links

- **Primary:** a single, high-contrast action per area. Ink on light; signature rose on dark. Use a concise verb: “Find my match”, “Build my kit”, “Add to bag”.
- **Secondary:** quiet outline or text action. It must never visually rival the primary button.
- **Text links:** use ink or deep rose with an obvious underline or underline-on-hover. Do not rely on colour alone.
- **Pressed / selected:** a subtle scale or surface shift is enough. Do not add bounce, glow, and colour changes together.

### Cards

- Cards group a decision, a product, or a meaningful next step. They are not default page decoration.
- Product cards place imagery first, then product name, relevance, shade/skin information, price, and one action.
- Recommendation cards make the rationale visible: match confidence, a short “why it suits you” explanation, and an easy way to compare or revise.
- Use one card surface family per section. Avoid mixing dark, blush, white, gradients, and heavy borders in the same grid.

### Forms and the advisor

- Every step should answer one simple question. Keep the active question, progress, and next action in immediate view.
- Clearly distinguish unselected, hovered, selected, disabled, and validation-error states.
- For image upload and skin analysis, explain what happens to the image in plain language and avoid medical or diagnostic visual cues.
- Results should lead with a human-friendly conclusion, then show the evidence and product options—not the other way round.

### Navigation

- The header is calm and legible; the product and recommendation experience are the hero.
- Use the existing editorial wordmark, restrained rule lines, and one clear “Build my kit” action.
- On mobile, prioritise search, bag, account, and a readable menu. Never shrink controls below touch-safe dimensions.

## Image and art direction

- Use natural, tactile product imagery with true-to-shade colour. Makeup photos must not distort a shade through aggressive filters.
- Prefer soft paper, stone, plant, fabric, and skin textures as backgrounds. Keep their contrast low enough that text remains primary.
- Use botanical detail as an accent: a partial leaf, abstract petal tone, or quiet ingredient close-up. One intentional visual is stronger than many small decorations.
- Use a dark immersive background only when it adds focus: the advisor, comparison, checkout, or a high-value editorial story. Do not make every screen dark.

## Layout patterns

- **Marketing / discovery:** generous editorial hero → curated categories or proof → product/editorial cards → quiet close.
- **Shopping:** clear filters and product rhythm; use imagery and whitespace rather than crowded borders.
- **Advisor:** context header → visible progress → one decision at a time → warm, celebratory results.
- **Checkout:** remove distraction; make totals, security, and next step obvious.
- Start with a single-column mobile layout. Add columns only when scanning or comparison genuinely improves.

## Motion

- Motion is soft, brief, and purposeful: 150–250ms for hover, menu, selection, and disclosure states.
- Prefer fade, small translation, or tiny scale changes. Avoid parallax, looping decoration, and animation that obscures a choice.
- Respect `prefers-reduced-motion` throughout.

## Quality bar

Before shipping a UI change, check:

1. Can a person identify the single primary action in three seconds?
2. Does the page use one consistent surface, type, radius, and button grammar?
3. Is the makeup/product imagery accurate enough to support a buying decision?
4. Are states, focus indicators, and touch targets accessible?
5. Has ornament been removed where typography, spacing, or imagery can carry the feeling instead?

## Do and don't

**Do**

- Lead with clarity, warmth, and a genuinely useful recommendation.
- Use the rose accent sparingly, so it retains value.
- Treat product imagery and real shade information as the visual hero.
- Keep dark journeys focused and light journeys breathable.
- Maintain the existing service logic and accessibility when changing presentation.

**Don't**

- Copy another brand’s visual identity, proprietary font, logo, campaign composition, or product photography.
- Turn every action into a pink pill or every section into a card.
- Add gradients, glows, shadows, or decorative leaves merely to make a screen feel “designed.”
- Hide advice, caveats, or next steps behind an elaborate visual treatment.
- Let a new screen invent a separate palette, type system, or interaction language.

## Working rule for future design tasks

Read this file before redesigning or adding a user-facing screen. When a request needs exploration, create 2–3 clearly differentiated directions first, but keep each direction within this YAFA VANAM system. Use reference brands only to name an abstract principle (for example, “editorial whitespace” or “warm botanical surfaces”), never as a cloning target.
