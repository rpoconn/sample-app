Code Standards
* Avoid multiple UI hooks in one file.  try to keep markup / JSX in a single block.
* Use 4px tab indent
* File names must be unique and say what the file is without its folder (`user_service.py`, not `service.py`). Exempt: `__init__.py`, `index.ts`, generated files.
* 

Backend (`backend/app/`)
* `<domain>/<domain>_models.py`, `_service.py`, `_deps.py`, `_routes.py`. Shared code in `core/`.
* Service over ~200 lines → `<domain>_service/` package, one module per use case.
* Tests mirror the layout: `tests/<domain>/test_<domain>_routes.py`. See backend/README.md#code-layout.

Frontend (`frontend/src/`)
* Avoid creating similar components, try to reuse existing components, or add customization properties to existing components.
* Directories camelCase: `components/<feature>/`, shared ones in `components/common/`, shared hooks in `hooks/`, routes in `routes/`.
* Components PascalCase `.tsx` (incl. `components/ui/`); every other file camelCase (`flags.ts`, `useAuth.ts`, `companyAdmin.tsx` route, `resetPassword.spec.ts`). Prefix generic names with the feature (`jurisdictionColumns.ts`).
* Don't edit generated code: `client/`, `routeTree.gen.ts`. shadcn adds kebab-case files to `components/ui/`; rename them to PascalCase.


Dev Instructions
* use bun and bunx where possible
