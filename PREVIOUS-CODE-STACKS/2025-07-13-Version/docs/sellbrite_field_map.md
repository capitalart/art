# Sellbrite Field Mapping

This table shows how artwork listing fields map to the Sellbrite product CSV columns.

| Sellbrite Column | Source Field / Value |
| ---------------- | ------------------- |
| Name | `title` |
| SKU | `sku` |
| Description | `description` (padded to 400 words if shorter) |
| Product Type | constant `Artwork` |
| Brand | constant `Robin Custance Art` |
| UPC | _blank_ |
| ISBN | _blank_ |
| ASIN | _blank_ |
| EAN | _blank_ |
| MPN | _blank_ |
| Cost | _blank_ |
| Price | `price` |
| Quantity | from `config.SELLBRITE_DEFAULT_QUANTITY` |
| Tags | `tags` joined with commas |
| Materials | `materials` joined with commas |
| Primary Colour | `primary_colour` |
| Secondary Colour | `secondary_colour` |
| Weight (oz) | constant `0` |
| Image 1..10 | `images` list in order |
| Category | constant `Art > Paintings` |
| Condition | constant `New` |
| Digital/Physical | constant `Physical` |
| Length (in) | _blank_ |
| Width (in) | _blank_ |
| Height (in) | _blank_ |
| Shipping Template | _blank_ |
| Product Note | _blank_ |
| Gift Message | _blank_ |
| Personalization | _blank_ |
| Personalization Instructions | _blank_ |
| Return Policy | _blank_ |
| Active | constant `Yes` |
| Published | constant `Yes` |

Only the columns present in the template are written. New columns may be added at the end of the template file without changing the export code.
