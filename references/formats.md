# File formats

The helper reads files the user already has. It writes two new files: a markdown draft for a person to read, and JSON with the same facts for a later check. Both are drafts in the user's workspace. Run it with Python 3.10 or newer. `plan-my-week` and `ad-results` are the skills that use it. The other five skills do not require Python.

Unknown keys are ignored. Their names are listed in `ignored_fields`. Their values are not copied, and they are not treated as instructions.

## Week plan input

JSON object. Required for a complete calendar:

| Field | Meaning |
| :--- | :--- |
| `business` | Trading name the user stated. |
| `audience` | Who the posts are for, in the user's words. |
| `destinations` | Non-empty list of place names, such as `Instagram`. |
| `timezone` | The user's label, such as `Europe/London`. Dates are not shifted. |
| `week_start` | `YYYY-MM-DD` in that label. |
| `offers` | Non-empty list of offers in the user's words. |

Optional: `voice` (string), `assets` (list of objects with `id`, and optional `path` and `note`), `claims_to_avoid` (list of strings), `cadence_per_destination` (integer 1 to 7). If cadence is omitted and the required fields are present, the helper uses 3 and sets `cadence_source` to `default_3_because_not_supplied`. A wrong cadence type is a gap, not a guess.

Asset ids are rotated across slots. Offers are rotated in slot order. Slot days for a cadence are fixed: 1 → day 0; 2 → days 0 and 3; 3 → days 0, 2 and 4; 4 → days 0, 2, 4 and 6; 5 → days 0, 1, 2, 4 and 6; 6 → days 0 through 5; 7 → every day.

Caption text is exactly `{business}: {offer}. For {audience}. {destination} on {weekday} {date}.` A supplied asset id adds ` Photo: {id}.` No other claim is added.

Exit 0 writes the files even when `status` is `incomplete`. Incomplete means no slots were written. Exit 2 means the file could not be read as the expected JSON or CSV. Exit 3 means an output path already exists and `--replace` was not set.

```text
python scripts/soclo_cursor_local.py plan --input brand.json --out week.md --json-out week.json
```

## Performance input

JSON object or CSV. Counts are whole numbers. Money fields are decimal numbers. `null`, an empty cell, `n/a`, `na`, `-`, or `none` means missing. A missing figure is not zero.

JSON:

```json
{
  "source": "instagram-export",
  "currency": "GBP",
  "period": {"start": "2026-10-01", "end": "2026-10-07"},
  "rows": [
    {
      "id": "post-1",
      "name": "Iced bun",
      "impressions": 1000,
      "clicks": 40,
      "spend": "20.00",
      "conversions": 4,
      "revenue": null
    }
  ]
}
```

CSV header, in this order, with the last four columns optional:

```text
id,name,impressions,clicks,spend,conversions,revenue,source,currency,period_start,period_end
```

Calculated only when both numbers exist and the divisor is not zero:

| Metric | Division |
| :--- | :--- |
| `ctr` | clicks / impressions, plus a percent |
| `cpc` | spend / clicks, in the file currency |
| `cpa` | spend / conversions |
| `click_conversion_rate` | conversions / clicks |
| `roas` | revenue / spend |

Each calculated metric includes `basis`, the two numbers divided. A total rate is calculated only when every row has both numbers. Sums of one column can exclude missing rows; those row ids are listed, and the partial sum is not used as a total rate.

`status` is `incomplete` when there is no row, a cell is not a number, or any row lacks impressions or clicks. Other missing metrics stay on the row as `unavailable` and do not become zeros.

```text
python scripts/soclo_cursor_local.py analyse --input export.json --out analysis.md --json-out analysis.json
```

`analyze` is the same command.

The input must be under 2 MB. Structural failure exits 2 and writes nothing.
