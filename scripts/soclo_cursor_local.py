"""Local calendar and performance drafts. Standard library only. No network."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

MAX_BYTES = 2_000_000
MAX_TEXT = 500
MONEY_Q = Decimal("0.01")
RATIO_Q = Decimal("0.0001")
PERCENT_Q = Decimal("0.01")
CADENCE_DAYS = {
    1: (0,),
    2: (0, 3),
    3: (0, 2, 4),
    4: (0, 2, 4, 6),
    5: (0, 1, 2, 4, 6),
    6: (0, 1, 2, 3, 4, 5),
    7: (0, 1, 2, 3, 4, 5, 6),
}
PLAN_KEYS = {
    "business",
    "audience",
    "voice",
    "offers",
    "destinations",
    "timezone",
    "assets",
    "claims_to_avoid",
    "week_start",
    "cadence_per_destination",
}
ASSET_KEYS = {"id", "path", "note"}
PLAN_REQUIRED = ("audience", "business", "destinations", "offers", "timezone", "week_start")
ANALYSE_KEYS = {"source", "currency", "period", "rows"}
ROW_KEYS = {"id", "name", "impressions", "clicks", "spend", "conversions", "revenue"}
COUNT_FIELDS = ("impressions", "clicks", "conversions")
MONEY_FIELDS = ("spend", "revenue")
MISSING_WORDS = {"", "null", "n/a", "na", "-", "none"}
PLAN_LIMITS = [
    "Draft only. Nothing is published or scheduled.",
    "Dates are labels in the supplied timezone. They are not a converted clock.",
    "Captions use only the supplied business, offer, audience, destination, date, and asset id.",
]
ANALYSE_LIMITS = [
    "A missing figure stays missing and is not treated as zero.",
    "A supplied zero stays zero.",
    "Rates are arithmetic on this file. They are not monetary ROI and they are not proof that a post caused a sale.",
]


class InputError(Exception):
    pass


class OutputExists(Exception):
    pass


def money(value: Decimal) -> str:
    return format(value.quantize(MONEY_Q, rounding=ROUND_HALF_UP), "f")


def ratio(value: Decimal) -> str:
    return format(value.quantize(RATIO_Q, rounding=ROUND_HALF_UP), "f")


def percent(value: Decimal) -> str:
    return format((value * Decimal(100)).quantize(PERCENT_Q, rounding=ROUND_HALF_UP), "f")


def show_count(value: Decimal) -> str:
    return str(int(value))


def unavailable(reason: str) -> dict:
    return {"status": "unavailable", "reason": reason}


def split_known(data: dict, allowed: set[str]) -> tuple[dict, list[str]]:
    known = {key: data[key] for key in data if key in allowed}
    ignored = sorted(key for key in data if key not in allowed)
    return known, ignored


def read_bytes(path: Path) -> str:
    if not path.is_file():
        raise InputError(f"input is not a file: {path}")
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise InputError("input is larger than 2 MB")
    return path.read_text(encoding="utf-8-sig")


def load_json_object(text: str) -> dict:
    try:
        data = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise InputError(f"input is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise InputError("input JSON must be an object")
    return data


def clean_string(value, field: str) -> str:
    if not isinstance(value, str):
        raise InputError(f"{field} must be a string")
    text = " ".join(value.split())
    if not text:
        raise InputError(f"{field} is empty")
    if len(text) > MAX_TEXT:
        raise InputError(f"{field} is longer than {MAX_TEXT} characters")
    return text


def optional_string(value, field: str):
    if value is None:
        return None
    return clean_string(value, field)


def string_list(value, field: str) -> list[str]:
    if not isinstance(value, list):
        raise InputError(f"{field} must be a list of strings")
    if len(value) > 40:
        raise InputError(f"{field} has more than 40 items")
    return [clean_string(item, field) for item in value]


def parse_metric(value, field: str, *, money_field: bool):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in MISSING_WORDS:
            return None
        try:
            number = Decimal(value.strip())
        except InvalidOperation:
            return field
    elif isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return field
    else:
        number = Decimal(value)
    if not number.is_finite() or number < 0:
        return field
    if not money_field and number != number.to_integral_value():
        return field
    return number


def caption_for(business: str, offer: str, audience: str, destination: str, weekday: str, when: str, asset_id: str | None) -> str:
    text = f"{business}: {offer}. For {audience}. {destination} on {weekday} {when}."
    if asset_id:
        text += f" Photo: {asset_id}."
    return text


def build_plan(raw: dict) -> dict:
    known, ignored = split_known(raw, PLAN_KEYS)
    gaps: list[str] = []
    parsed: dict = {}
    for field in ("business", "audience", "timezone", "week_start", "voice"):
        if field not in known:
            if field != "voice":
                gaps.append(field)
            continue
        try:
            parsed[field] = clean_string(known[field], field)
        except InputError:
            gaps.append(field)
    if "week_start" in parsed:
        try:
            parsed["week_start_date"] = datetime.strptime(parsed["week_start"], "%Y-%m-%d").date()
        except ValueError:
            gaps.append("week_start")
    for field in ("offers", "destinations", "claims_to_avoid"):
        if field not in known:
            if field != "claims_to_avoid":
                gaps.append(field)
            continue
        try:
            items = string_list(known[field], field)
        except InputError:
            gaps.append(field)
            continue
        if field != "claims_to_avoid" and not items:
            gaps.append(field)
        else:
            parsed[field] = items
    assets: list[dict] = []
    if "assets" in known:
        raw_assets = known["assets"]
        if not isinstance(raw_assets, list):
            gaps.append("assets")
        else:
            for item in raw_assets:
                if not isinstance(item, dict):
                    gaps.append("assets")
                    break
                asset_known, asset_ignored = split_known(item, ASSET_KEYS)
                ignored.extend(f"assets.{name}" for name in asset_ignored)
                try:
                    asset_id = clean_string(asset_known.get("id"), "assets.id")
                except InputError:
                    gaps.append("assets")
                    break
                note = item.get("note")
                path = item.get("path")
                try:
                    assets.append(
                        {
                            "id": asset_id,
                            "path": None if path is None else clean_string(path, "assets.path"),
                            "note": None if note is None else clean_string(note, "assets.note"),
                        }
                    )
                except InputError:
                    gaps.append("assets")
                    break
    cadence_source = None
    cadence = None
    if "cadence_per_destination" not in known:
        cadence = 3
        cadence_source = "default_3_because_not_supplied"
    else:
        raw_cadence = known["cadence_per_destination"]
        if isinstance(raw_cadence, bool) or not isinstance(raw_cadence, int) or raw_cadence not in CADENCE_DAYS:
            gaps.append("cadence_per_destination")
        else:
            cadence = raw_cadence
            cadence_source = "supplied"
    gaps = sorted(set(gaps))
    if gaps and cadence_source == "default_3_because_not_supplied":
        cadence = None
        cadence_source = None
    result = {
        "kind": "week-plan",
        "status": "incomplete" if gaps else "complete",
        "gaps": gaps,
        "ignored_fields": sorted(set(ignored)),
        "business": parsed.get("business"),
        "audience": parsed.get("audience"),
        "timezone": parsed.get("timezone"),
        "week_start": parsed.get("week_start") if "week_start" not in gaps else None,
        "voice": parsed.get("voice"),
        "claims_to_avoid": parsed.get("claims_to_avoid", []),
        "cadence_per_destination": cadence if "cadence_per_destination" not in gaps else None,
        "cadence_source": cadence_source if "cadence_per_destination" not in gaps else None,
        "posts": [],
        "limits": PLAN_LIMITS,
    }
    if gaps:
        return result
    start = parsed["week_start_date"]
    offers = parsed["offers"]
    destinations = parsed["destinations"]
    slot_index = 0
    for offset in CADENCE_DAYS[cadence]:
        slot_date = start + timedelta(days=offset)
        for destination in destinations:
            offer = offers[slot_index % len(offers)]
            asset = assets[slot_index % len(assets)] if assets else None
            result["posts"].append(
                {
                    "date": slot_date.isoformat(),
                    "weekday": slot_date.strftime("%A"),
                    "destination": destination,
                    "format": "photo post" if asset else "text post",
                    "audience": parsed["audience"],
                    "offer": offer,
                    "asset_id": None if asset is None else asset["id"],
                    "asset_path": None if asset is None else asset["path"],
                    "asset_note": None if asset is None else asset["note"],
                    "voice": parsed.get("voice"),
                    "do_not_claim": parsed.get("claims_to_avoid", []),
                    "caption": caption_for(
                        parsed["business"],
                        offer,
                        parsed["audience"],
                        destination,
                        slot_date.strftime("%A"),
                        slot_date.isoformat(),
                        None if asset is None else asset["id"],
                    ),
                }
            )
            slot_index += 1
    return result


def render_plan(plan: dict) -> str:
    lines = [
        "# Week draft",
        "",
        f"Status: {plan['status']}",
        f"Business: {plan['business'] or 'not supplied'}",
        f"Timezone: {plan['timezone'] or 'not supplied'}",
        f"Week start: {plan['week_start'] or 'not supplied'}",
        f"Cadence per destination: {plan['cadence_per_destination'] if plan['cadence_per_destination'] is not None else 'not supplied'}",
        f"Cadence source: {plan['cadence_source'] or 'not supplied'}",
        "",
        plan["limits"][0],
        plan["limits"][1],
        "",
        "## Gaps",
        "",
    ]
    lines.extend(f"- {gap}" for gap in plan["gaps"])
    if not plan["gaps"]:
        lines.append("None.")
    lines.extend(["", "## Slots", ""])
    if not plan["posts"]:
        lines.append("No slots were written.")
    for post in plan["posts"]:
        lines.extend(
            [
                f"### {post['date']} {post['weekday']} — {post['destination']} — {post['format']}",
                "",
                f"- Audience: {post['audience']}",
                f"- Offer: {post['offer']}",
                f"- Asset id: {post['asset_id'] or 'none supplied'}",
                f"- Asset note: {post['asset_note'] or 'none supplied'}",
                f"- Voice: {post['voice'] or 'not supplied'}",
                "- Do not claim: " + ("; ".join(post["do_not_claim"]) if post["do_not_claim"] else "none supplied"),
                f"- Caption: {post['caption']}",
                "",
            ]
        )
    lines.extend(["## Limits", ""])
    lines.extend(f"- {item}" for item in plan["limits"])
    lines.append("")
    return "\n".join(lines)


def metric_pair(numer, denom, numer_name: str, denom_name: str, *, style: str, numer_money: bool, denom_money: bool):
    if isinstance(numer, str) or isinstance(denom, str):
        return unavailable("value_not_a_number")
    if numer is None:
        return unavailable(f"{numer_name}_missing")
    if denom is None:
        return unavailable(f"{denom_name}_missing")
    if denom == 0:
        return unavailable(f"{denom_name}_zero")
    value = numer / denom
    shown_numer = money(numer) if numer_money else show_count(numer)
    shown_denom = money(denom) if denom_money else show_count(denom)
    shown_value = money(value) if style == "money" else ratio(value)
    out = {"status": "calculated", "value": shown_value, "basis": f"{shown_numer}/{shown_denom}"}
    if numer_name == "clicks" and denom_name == "impressions":
        out["percent"] = percent(value)
    return out


def summarise_column(rows: list[dict], field: str, *, money_field: bool):
    present = []
    excluded = []
    for row in rows:
        value = row["parsed"][field]
        if isinstance(value, str):
            return {"status": "unavailable", "reason": "value_not_a_number", "excluded_ids": []}
        if value is None:
            excluded.append(row["id"])
        else:
            present.append(value)
    if not present:
        return {"status": "unavailable", "reason": "all_missing", "excluded_ids": excluded}
    total = sum(present, Decimal(0))
    shown = money(total) if money_field else show_count(total)
    status = "complete" if not excluded else "partial_sum"
    return {"status": status, "value": shown, "excluded_ids": excluded}


def rate_total(rows: list[dict], numer_name: str, denom_name: str, *, style: str, numer_money: bool, denom_money: bool):
    for row in rows:
        numer = row["parsed"][numer_name]
        denom = row["parsed"][denom_name]
        if numer is None or denom is None or isinstance(numer, str) or isinstance(denom, str):
            return unavailable("incomplete_rows")
    numer_sum = sum((row["parsed"][numer_name] for row in rows), Decimal(0))
    denom_sum = sum((row["parsed"][denom_name] for row in rows), Decimal(0))
    return metric_pair(
        numer_sum,
        denom_sum,
        numer_name,
        denom_name,
        style=style,
        numer_money=numer_money,
        denom_money=denom_money,
    )


def row_metrics(parsed: dict) -> dict:
    return {
        "ctr": metric_pair(
            parsed["clicks"], parsed["impressions"], "clicks", "impressions",
            style="ratio", numer_money=False, denom_money=False,
        ),
        "cpc": metric_pair(
            parsed["spend"], parsed["clicks"], "spend", "clicks",
            style="money", numer_money=True, denom_money=False,
        ),
        "cpa": metric_pair(
            parsed["spend"], parsed["conversions"], "spend", "conversions",
            style="money", numer_money=True, denom_money=False,
        ),
        "click_conversion_rate": metric_pair(
            parsed["conversions"], parsed["clicks"], "conversions", "clicks",
            style="ratio", numer_money=False, denom_money=False,
        ),
        "roas": metric_pair(
            parsed["revenue"], parsed["spend"], "revenue", "spend",
            style="ratio", numer_money=True, denom_money=True,
        ),
    }


def display_input(parsed: dict) -> dict:
    shown = {}
    for field in COUNT_FIELDS:
        value = parsed[field]
        shown[field] = None if value is None or isinstance(value, str) else int(value)
    for field in MONEY_FIELDS:
        value = parsed[field]
        shown[field] = None if value is None or isinstance(value, str) else money(value)
    return shown


def build_analyse(raw: dict) -> dict:
    known, ignored = split_known(raw, ANALYSE_KEYS)
    missing_context = []
    source = optional_string(known["source"], "source") if "source" in known else None
    currency = optional_string(known["currency"], "currency") if "currency" in known else None
    period = {"start": None, "end": None}
    if "period" not in known or known["period"] is None:
        missing_context.append("period")
    elif not isinstance(known["period"], dict):
        raise InputError("period must be an object")
    else:
        period_known, period_ignored = split_known(known["period"], {"start", "end"})
        ignored.extend(f"period.{name}" for name in period_ignored)
        for side in ("start", "end"):
            if side not in period_known or period_known[side] in (None, ""):
                missing_context.append("period")
            else:
                text = clean_string(period_known[side], f"period.{side}")
                datetime.strptime(text, "%Y-%m-%d")
                period[side] = text
        if period["start"] is None or period["end"] is None:
            missing_context.append("period")
    if "source" not in known:
        missing_context.append("source")
    if "currency" not in known:
        missing_context.append("currency")
    rows_raw = known.get("rows")
    field_gap = []
    parsed_rows = []
    if not isinstance(rows_raw, list) or not rows_raw:
        field_gap.append("no_rows")
        rows_raw = []
    for index, item in enumerate(rows_raw):
        if not isinstance(item, dict):
            raise InputError("each row must be an object")
        row_known, row_ignored = split_known(item, ROW_KEYS)
        ignored.extend(f"rows.{name}" for name in row_ignored)
        row_id = clean_string(row_known.get("id", f"row-{index + 1}"), "id") if "id" in row_known else f"row-{index + 1}"
        name = clean_string(row_known["name"], "name") if "name" in row_known else None
        parsed = {}
        errors = []
        for field in COUNT_FIELDS + MONEY_FIELDS:
            value = parse_metric(row_known.get(field), field, money_field=field in MONEY_FIELDS)
            if isinstance(value, str):
                errors.append({"field": field, "reason": "value_not_a_number"})
                parsed[field] = None
            else:
                parsed[field] = value
        parsed_rows.append(
            {
                "id": row_id,
                "name": name,
                "parsed": parsed,
                "field_errors": errors,
            }
        )
    rows_out = []
    for row in parsed_rows:
        rows_out.append(
            {
                "id": row["id"],
                "name": row["name"],
                "input": display_input(row["parsed"]),
                "field_errors": row["field_errors"],
                "metrics": row_metrics(row["parsed"]),
            }
        )
    incomplete = bool(field_gap) or any(row["field_errors"] for row in parsed_rows)
    if any(row["parsed"]["impressions"] is None or row["parsed"]["clicks"] is None for row in parsed_rows):
        incomplete = True
    if parsed_rows:
        totals = {
            "impressions": summarise_column(parsed_rows, "impressions", money_field=False),
            "clicks": summarise_column(parsed_rows, "clicks", money_field=False),
            "spend": summarise_column(parsed_rows, "spend", money_field=True),
            "conversions": summarise_column(parsed_rows, "conversions", money_field=False),
            "revenue": summarise_column(parsed_rows, "revenue", money_field=True),
            "ctr": rate_total(parsed_rows, "clicks", "impressions", style="ratio", numer_money=False, denom_money=False),
            "cpc": rate_total(parsed_rows, "spend", "clicks", style="money", numer_money=True, denom_money=False),
            "cpa": rate_total(parsed_rows, "spend", "conversions", style="money", numer_money=True, denom_money=False),
            "click_conversion_rate": rate_total(
                parsed_rows, "conversions", "clicks", style="ratio", numer_money=False, denom_money=False
            ),
            "roas": rate_total(parsed_rows, "revenue", "spend", style="ratio", numer_money=True, denom_money=True),
        }
    else:
        names = (
            "impressions", "clicks", "spend", "conversions", "revenue",
            "ctr", "cpc", "cpa", "click_conversion_rate", "roas",
        )
        totals = {name: unavailable("no_rows") for name in names}
    return {
        "kind": "performance-analysis",
        "status": "incomplete" if incomplete else "complete",
        "gaps": sorted(set(field_gap)),
        "missing_context": sorted(set(missing_context)),
        "ignored_fields": sorted(set(ignored)),
        "source": source,
        "currency": currency,
        "period": period,
        "rows": rows_out,
        "totals": totals,
        "limits": ANALYSE_LIMITS,
    }


def render_analyse(report: dict) -> str:
    lines = [
        "# Performance draft",
        "",
        f"Status: {report['status']}",
        f"Source: {report['source'] or 'not supplied'}",
        f"Currency: {report['currency'] or 'not supplied'}",
        f"Period start: {report['period']['start'] or 'not supplied'}",
        f"Period end: {report['period']['end'] or 'not supplied'}",
        "",
        report["limits"][0],
        report["limits"][2],
        "",
        "## Rows",
        "",
    ]
    if not report["rows"]:
        lines.append("No rows were supplied.")
    for row in report["rows"]:
        lines.extend([f"### {row['id']}", "", f"- Name: {row['name'] or 'not supplied'}"])
        for field, value in row["input"].items():
            lines.append(f"- {field}: {'missing' if value is None else value}")
        for name, metric in row["metrics"].items():
            if metric["status"] == "calculated":
                extra = f" ({metric['percent']}%)" if "percent" in metric else ""
                lines.append(f"- {name}: {metric['value']}{extra}; basis {metric['basis']}")
            else:
                lines.append(f"- {name}: unavailable ({metric['reason']})")
        lines.append("")
    lines.extend(["## Totals", ""])
    for name, total in report["totals"].items():
        if total["status"] == "calculated":
            extra = f" ({total['percent']}%)" if "percent" in total else ""
            lines.append(f"- {name}: {total['value']}{extra}; basis {total['basis']}")
        elif total["status"] in {"complete", "partial_sum"}:
            excluded = ", ".join(total["excluded_ids"]) or "none"
            lines.append(f"- {name}: {total['value']} ({total['status']}; excluded {excluded})")
        else:
            lines.append(f"- {name}: unavailable ({total['reason']})")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in report["limits"])
    lines.append("")
    return "\n".join(lines)


def rows_from_csv(text: str) -> dict:
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise InputError("CSV has no header")
    header = [name.strip() for name in reader.fieldnames]
    required = ["id", "name", "impressions", "clicks", "spend", "conversions", "revenue"]
    if header[:7] != required:
        raise InputError("CSV header must start with id,name,impressions,clicks,spend,conversions,revenue")
    rows = []
    metas = []
    for record in reader:
        if record is None:
            continue
        if all(not (record.get(name) or "").strip() for name in required):
            continue
        row = {name: record.get(name) for name in required}
        rows.append(row)
        metas.append({name: (record.get(name) or "").strip() for name in ("source", "currency", "period_start", "period_end")})
    raw = {"rows": rows}
    if not metas:
        return raw
    def same(field: str):
        values = {item[field] for item in metas}
        return next(iter(values)) if len(values) == 1 else None
    source = same("source")
    currency = same("currency")
    start = same("period_start")
    end = same("period_end")
    if source:
        raw["source"] = source
    if currency:
        raw["currency"] = currency
    if start or end:
        raw["period"] = {"start": start or None, "end": end or None}
    return raw


def prepare_output(path: Path, replace: bool) -> None:
    if path.exists() and not replace:
        raise OutputExists(str(path))
    if path.exists() and path.is_dir():
        raise InputError(f"output is a directory: {path}")
    parent = path.parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def write_pair(markdown_path: Path, json_path: Path, markdown: str, payload: dict, replace: bool) -> None:
    prepare_output(markdown_path, replace)
    prepare_output(json_path, replace)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    markdown_path.write_text(markdown, encoding="utf-8", newline="\n")


def run(command: str, input_path: Path, markdown_path: Path, json_path: Path, replace: bool) -> dict:
    resolved = {input_path.resolve(), markdown_path.resolve(), json_path.resolve()}
    if len(resolved) < 3:
        raise InputError("input, markdown output, and JSON output must be three different files")
    text = read_bytes(input_path)
    if command == "plan":
        payload = build_plan(load_json_object(text))
        markdown = render_plan(payload)
    else:
        if input_path.suffix.lower() == ".csv":
            raw = rows_from_csv(text)
        else:
            raw = load_json_object(text)
        payload = build_analyse(raw)
        markdown = render_analyse(payload)
    write_pair(markdown_path, json_path, markdown, payload, replace)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soclo_cursor_local")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "analyse", "analyze"):
        command = sub.add_parser(name)
        command.add_argument("--input", required=True)
        command.add_argument("--out", required=True)
        command.add_argument("--json-out", required=True)
        command.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    command = "plan" if args.command == "plan" else "analyse"
    try:
        payload = run(
            command,
            Path(args.input),
            Path(args.out),
            Path(args.json_out),
            args.replace,
        )
    except OutputExists as exc:
        print(f"output already exists: {exc}", file=sys.stderr)
        return 3
    except (InputError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(payload["kind"] + " " + payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
