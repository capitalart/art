# Codex Patch Log – 2025-07-21

## Summary
- Fixed registry loader to enforce dictionary structure and avoid list-index errors
- Updated multiple routes to use `load_json_file_safe`
- Rewrote upload.js to use `fetch` with proper JSON handling
- Added docstrings and comments
- All tests passing

## Files Modified
- `routes/utils.py`
- `routes/artwork_routes.py`
- `static/js/upload.js` (rewritten)

## Manual Steps
- `pytest -q` executed – all 24 tests passed

