# Sellbrite Export Usage

1. Update `docs/csv_product_template.csv` if Sellbrite releases a new template. Ensure the header row reflects the exact column order.
2. Adjust any field mappings in `scripts/sellbrite_csv_export.py` if new columns are added.
3. In the Flask UI, visit **Exports** and click **Export Now** to generate a CSV of all finalised artworks. Locked-only and test exports are available from the same page.
4. Download the generated CSV and import it into Sellbrite or Etsy.

See [`CSV_EXPORT.md`](CSV_EXPORT.md) for detailed instructions on updating the template and remapping fields.
See [`Sellbrite_CSV_Format.md`](Sellbrite_CSV_Format.md) for details on the generated CSV structure and a sample command.
