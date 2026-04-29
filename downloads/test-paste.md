# Q3 Product Notes — Athena release

**TL;DR.** Hit 92% of feature goals; latency regressed 14% and we owe a fix in Q4.

## Wins

- Shipped block editor + per-type preview (#14)
- Migrated 3 services to **Haiku 4.5** with no quality regression
- Cut Pinecone cold-start from 1.2s → 380ms

## Open risks

1. PDF viewer pulls 600KB on first open — *acceptable for now*
2. CSV preview capped at 1,000 rows
3. BlockNote slash menu has no keyboard shortcuts for embed-by-URL

## Decision log

> "Ship the editor as markdown-output, not JSON. Cheaper to roll back and the chunker doesn't care."
> — eng review, 2026-04-22

## Code reference

```ts
function chunk(md: string, max = 200): string[] {
  return splitIntoTokens(md).reduce(intoChunks(max), []);
}
```

## Links

- [BlockNote docs](https://www.blocknotejs.org)
- [pdf.js text layer](https://mozilla.github.io/pdf.js)

## What to test

| Feature | Tested? |
|---|---|
| Headings render | ☐ |
| Bullet + numbered lists | ☐ |
| Bold / italic / blockquote | ☐ |
| Fenced code block | ☐ |
| Table | ☐ |
| Link click | ☐ |
