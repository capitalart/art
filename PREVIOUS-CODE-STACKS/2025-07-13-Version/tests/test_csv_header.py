import csv
from pathlib import Path

import scripts.sellbrite_csv_export as sb


def test_template_header_matches_file():
    template = Path('docs/csv_product_template.csv')
    expected = sb.read_template_header(template)

    with open(template, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
        if rows and rows[0] and rows[0][0].startswith('SELLBRITE PRODUCT CSV'):
            actual_row = rows[2] if len(rows) >= 3 else rows[-1]
        else:
            actual_row = rows[0] if rows else []
        actual = [h.strip() for h in actual_row]

    assert expected == actual
