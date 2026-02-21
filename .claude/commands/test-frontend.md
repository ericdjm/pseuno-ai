# Test Frontend

Validate frontend changes compile, lint, and build correctly.

## Steps

### 1. Type check

```bash
cd frontend && npx tsc --noEmit
```
Must have zero errors.

### 2. Lint

```bash
cd frontend && npm run lint
```
Must have zero warnings (strict policy).

### 3. Build

```bash
cd frontend && npm run build
```
Must succeed.

### 4. E2E tests (if dev stack is running)

```bash
cd frontend && npx playwright test
```

### 5. Visual verification (if making UI changes)

Open `localhost:5173` in a browser (via Playwright MCP) and visually verify the change looks correct.
