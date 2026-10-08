Code Standards
* Avoid multiple UI hooks in one file.  try to keep markup / JSX in a single block.
* Use 4px tab indent
* Backend: organize by business domain, then by kind (`models.py`, `service.py`, `deps.py`, `routes.py`). Split a service over ~200 lines into a `service/` package with one module per use case. See backend/README.md#code-layout.


Dev Instructions
* use bun and bunx where possible