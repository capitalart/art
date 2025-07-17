# Sellbrite CSV Format

The `scripts/sellbrite_csv_export.py` tool writes CSV files that match the official Sellbrite product template. The first row is copied directly from `docs/csv_product_template.csv` so all column names appear exactly as Sellbrite expects.

Required columns are validated before export:

- `sku`
- `name`
- `description`
- `price`

If any of these are missing in the template or a row, the export fails with an error message.

A sample export can be generated using the Flask UI under **Exports** or by running:

```bash
python scripts/sellbrite_csv_export.py docs/csv_product_template.csv sample.csv --json-dir outputs/finalised-artwork
```

The resulting `sample.csv` will be ready for immediate import into Sellbrite/Etsy.
