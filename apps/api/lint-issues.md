# MyPy Lint Issues Analysis

## Summary
Found 16 errors across 4 files in the authentication domain. Issues include missing type annotations, incorrect model references, missing dependencies, and Prisma model naming mismatches.

---

## src/domains/auth/service.py

### Error 1: Missing supabase module
```
src/domains/auth/service.py:3: error: Cannot find implementation or library stub for module named "supabase"  [import-not-found]
```
**Explanation**: MyPy cannot find the `supabase` Python package.
**Solution**: Install the supabase client library: `poetry add supabase` or add type stubs if using a different package.

### Error 2-4: Missing return type annotations
```
src/domains/auth/service.py:15: error: Function is missing a return type annotation  [no-untyped-def]
src/domains/auth/service.py:21: error: Function is missing a return type annotation  [no-untyped-def]
src/domains/auth/service.py:27: error: Function is missing a return type annotation  [no-untyped-def]
```
**Explanation**: Functions at lines 15, 21, and 27 need explicit return type annotations.
**Solution**: Add return types like `-> None`, `-> str`, `-> dict`, etc. to each function.

### Error 5: Prisma type mismatch
```
src/domains/auth/service.py:53: error: Argument "where" to "find_first" of "organization_membersActions" has incompatible type "dict[str, int | str]"; expected "organization_membersWhereInput | None"  [arg-type]
```
**Explanation**: Passing a raw dict instead of proper Prisma WhereInput type.
**Solution**: Use proper Prisma query syntax or cast the dict to the expected type.

---

## src/domains/auth/models.py

### Error 6: Incorrect Profile model reference
```
src/domains/auth/models.py:4: error: Module "prisma.models" has no attribute "Profile"; maybe "profiles"?  [attr-defined]
```
**Explanation**: The model should be `profiles` (lowercase) not `Profile`.
**Solution**: Change `from prisma.models import Profile` to `from prisma.models import profiles`.

### Error 7: Missing projects module
```
src/domains/auth/models.py:7: error: Cannot find implementation or library stub for module named "src.domains.projects.models"  [import-not-found]
```
**Explanation**: The projects domain doesn't exist or isn't properly structured.
**Solution**: Either create the projects module or remove the import if not needed.

---

## src/domains/auth/dependencies.py

### Error 8: Missing jwt module
```
src/domains/auth/dependencies.py:2: error: Cannot find implementation or library stub for module named "jwt"  [import-not-found]
```
**Explanation**: Missing PyJWT library.
**Solution**: Install PyJWT: `poetry add pyjwt` and ensure proper imports.

### Error 9: Incorrect Profile model reference
```
src/domains/auth/dependencies.py:5: error: Module "prisma.models" has no attribute "Profile"; maybe "profiles"?  [attr-defined]
```
**Explanation**: Same issue as models.py - should be `profiles`.
**Solution**: Change import to use `profiles` instead of `Profile`.

### Error 10: Missing return type annotation
```
src/domains/auth/dependencies.py:17: error: Function is missing a return type annotation  [no-untyped-def]
```
**Explanation**: Function at line 17 needs a return type.
**Solution**: Add appropriate return type annotation.

### Error 11: Any return type
```
src/domains/auth/dependencies.py:54: error: Returning Any from function declared to return "str"  [no-any-return]
```
**Explanation**: Function returns `Any` but is annotated to return `str`.
**Solution**: Ensure the function actually returns a string or fix the type annotation.

### Error 12: Incorrect Prisma model name
```
src/domains/auth/dependencies.py:63: error: "Prisma" has no attribute "authlink"; maybe "auth_links"?  [attr-defined]
```
**Explanation**: Prisma model should be `auth_links` (snake_case) not `authlink`.
**Solution**: Change `db.authlink` to `db.auth_links`.

---

## src/domains/auth/routes.py

### Error 13: Incorrect Profile model reference
```
src/domains/auth/routes.py:3: error: Module "prisma.models" has no attribute "Profile"; maybe "profiles"?  [attr-defined]
```
**Explanation**: Same Profile/profiles naming issue.
**Solution**: Use `profiles` instead of `Profile`.

### Error 14: Missing projects module
```
src/domains/auth/routes.py:9: error: Cannot find implementation or library stub for module named "src.domains.projects.models"  [import-not-found]
```
**Explanation**: Projects domain missing.
**Solution**: Create projects module or remove import.

### Error 15: Missing return type annotation
```
src/domains/auth/routes.py:20: error: Function is missing a return type annotation  [no-untyped-def]
```
**Explanation**: Function needs return type.
**Solution**: Add return type annotation.

### Error 16: Incorrect Prisma model name
```
src/domains/auth/routes.py:23: error: "Prisma" has no attribute "project"  [attr-defined]
```
**Explanation**: Should be `projects` (plural) not `project`.
**Solution**: Change to `db.projects`.

---

## Recommended Action Plan

1. **Fix Prisma model names**: Change all `Profile` to `profiles`, `authlink` to `auth_links`, `project` to `projects`
2. **Install missing dependencies**: `poetry add supabase pyjwt`
3. **Add missing return type annotations** to all functions
4. **Create or remove projects domain** references
5. **Fix Prisma query types** to use proper WhereInput types
6. **Verify Prisma schema** matches the model names being used in code