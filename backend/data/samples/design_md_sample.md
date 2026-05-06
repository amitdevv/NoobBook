# Design Specification — {{Your Brand}}

> One source of truth for how generated content should look, sound, and feel.
> Studio agents (presentations, blogs, emails, websites, components, business
> reports, wireframes) read this file as part of their system prompt.

---

## 1. Brand Identity

**Name**: {{Your Brand}}
**One-liner**: {{What your brand does in a single sentence}}
**Audience**: {{Who you're talking to — be specific}}
**Industry**: {{e.g. SaaS, fintech, education, healthcare}}

### Mission
{{2-3 sentences. What you're trying to change in the world.}}

### Core values
- {{Value 1 — e.g. Clarity over cleverness}}
- {{Value 2 — e.g. Respect the reader's time}}
- {{Value 3 — e.g. Show, don't tell}}

---

## 2. Color Tokens

The brand-kit's structured color settings are the source of truth for hex values.
Use this section to describe **intent and pairing rules** the structured tokens
can't express.

- **Primary** ({{Primary color}}) — Use for: headers, key CTAs, brand moments. Avoid: large body text, muted contexts.
- **Accent** — Use for: links, interactive states, emphasis. Pairs with primary on dark backgrounds.
- **Neutrals** — Body text on near-white background; reverse on dark sections. Maintain WCAG AA contrast (4.5:1) for text under 18px.
- **Forbidden combinations**: {{e.g. "Never put accent on primary — both are saturated and vibrate"}}

---

## 3. Typography

- **Headings**: bold, generous line-height (1.2-1.3). Sentence case for H2+, Title Case for H1 only.
- **Body**: 16px minimum, line-height 1.6, max measure ~70 characters per line.
- **Hierarchy**: H1 → H2 → H3 only — skipping levels breaks scannability.
- **Numerals in tables**: tabular-nums so columns align.
- **Code/inline mono**: only for literal code, paths, or commands — not for emphasis.

---

## 4. Layout & Spacing

- **Grid**: 12-column on desktop, 4-column on mobile. Default gutter = 24px.
- **Section rhythm**: Generous vertical padding (96-128px on desktop) between sections — never let two sections crash into each other.
- **Component spacing**: Use 8px base unit. Multiples of 8 for all margins/paddings unless typography opts you out.
- **Edge density**: Avoid edge-to-edge content on desktop above 1280px — cap content width at 1200px.

---

## 5. Components

### Buttons
- **Primary**: filled primary color, white text, 8px radius, 12-16px vertical padding.
- **Secondary**: ghost (transparent fill, 1px border in primary), same dimensions.
- **Tertiary**: text-only with underline on hover.
- **Never**: 4 buttons in a row, gradient fills, drop shadows.

### Cards
- 12px radius, soft shadow (`0 2px 8px rgba(0,0,0,0.06)`), 1px border in neutral-100.
- Internal padding: 24px on desktop, 16px on mobile.

### Forms
- Labels above inputs, never inside (placeholder ≠ label).
- Inline validation, error in destructive color with one-line guidance.
- Submit button right-aligned, secondary action to its left.

### Imagery
- {{e.g. "Photographic, never illustrated"}}
- {{e.g. "Real customers/teams, never stock"}}
- {{e.g. "Crop tight on faces, leave breathing room around objects"}}

---

## 6. Voice & Tone

**Voice attributes** (constant): {{e.g. clear, direct, warm, never patronizing}}
**Tone shifts** (situational):
- **Marketing/landing**: confident, benefit-led, fewer words.
- **Onboarding**: encouraging, step-by-step, anticipatory.
- **Errors**: factual + recovery action, never blame the user.
- **Reports**: precise, data-first, conclusions before evidence.

### Words we use
{{primary_keyword_1, primary_keyword_2, primary_keyword_3, ...}}

### Words we don't
- "{{e.g. solution}}", "{{leverage}}", "{{utilize}}", "{{unlock}}" — too generic.
- "{{simply}}", "{{just}}", "{{easy}}" — patronizing.
- Anything that requires reading twice.

### Examples

**Good**: "Set up takes about 90 seconds. We'll email when it's ready."
**Bad**: "Embark on your transformation journey by leveraging our intuitive onboarding solution."

**Good**: "Couldn't connect to your database. Check that the host is reachable from this network and try again."
**Bad**: "An error occurred. Please try again later."

---

## 7. Accessibility

- All text ≥ WCAG AA contrast ratio.
- Interactive elements have visible focus rings — never `outline: none` without a replacement.
- Forms always have labels; icons used as buttons always have aria-labels.
- Avoid color-only signals (status, error, success) — pair with icon or text.
- Animations respect `prefers-reduced-motion`.

---

## 8. Don't Do

- Don't use rounded corners > 16px (gimmicky).
- Don't pair more than 2 typefaces.
- Don't use emoji as section markers in serious content.
- Don't bury the most important information below the fold.
- Don't show the brand logo in every component — once per page is enough.
- Don't add gradients to text.

---

*Edit this file freely — slot values like `{{Your Brand}}` are placeholders for
your team to fill in. Studio agents will follow whatever you write here as
binding guidance during generation.*
