---
description: Pre-commit checks to run before pushing changes
---

# Pre-Commit Checklist

Before committing and pushing changes, run these checks:

## 1. TypeScript/ESLint Check (for web app changes)

If you modified files in `apps/web/`:

// turbo
```bash
cd apps/web && npm run lint
```

This catches:
- Unused imports (like `Zap` that was removed but not from imports)
- TypeScript errors
- ESLint violations

## 2. Python Syntax Check (for professor-impetus changes)

If you modified files in `services/professor-impetus/`:

// turbo
```bash
cd services/professor-impetus && python -m py_compile app/main.py
```

## 3. Build Check (for significant web changes)

For significant changes, run a full build:

```bash
cd apps/web && npm run build
```

## Common Issues to Watch For

1. **Unused imports** - When removing JSX elements, also remove their imports
2. **Missing imports** - When adding new components, ensure they're imported
3. **Type errors** - Ensure props match expected types
