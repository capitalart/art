# Sellbrite Integration

This document outlines how the application communicates with the Sellbrite API when artwork is finalised.

## Workflow

1. **Lock Artwork** – When an artwork is marked as locked via the Finalised gallery, `routes.artwork_routes.lock_listing` writes the `locked` flag and then sends the product data to Sellbrite using `SellbriteAPI.create_product()`.
2. **API Utility** – `utils/sellbrite_api.py` loads `SELLBRITE_TOKEN` and `SELLBRITE_SECRET` from `.env` and exposes simple methods for authentication, listing products and creating them.
3. **Manual Push** – The endpoint `/finalise/push-sellbrite/<aspect>/<filename>` allows admins to resend a listing to Sellbrite on demand.

## Configuration

Set the following in your `.env` file:

```
SELLBRITE_TOKEN=your-token
SELLBRITE_SECRET=your-secret
```

Optional: `SELLBRITE_API_BASE` to override the default base URL.

## Notes

- The API payload is generated with `generate_sellbrite_json()` and includes `quantity` from `config.SELLBRITE_DEFAULT_QUANTITY`.
- Errors are logged and surfaced via flash messages in the admin interface.
- See `docs/sellbrite_field_map.md` for field mapping details.
