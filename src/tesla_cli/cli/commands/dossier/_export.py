"""``dossier`` commands — export (see ``__init__.py``).

Names tests patch on ``tesla_cli.cli.commands.dossier`` are looked up as ``_m.<name>``.
"""

from __future__ import annotations

from tesla_cli.cli.commands.dossier import (  # noqa: F401
    console,
    typer,
)


def dossier_export_pdf(
    output: str = typer.Option("dossier.pdf", "--output", "-o", help="Output PDF file path"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
) -> None:
    """Export the dossier to a formatted PDF report.

    tesla dossier export-pdf
    tesla dossier export-pdf --output ~/Desktop/my-tesla.pdf
    """
    try:
        from fpdf import FPDF  # type: ignore[import]
    except ImportError:
        console.print(
            "[red]fpdf2 is required for PDF export.[/red]\n"
            "Install with: [bold]uv pip install fpdf2[/bold]"
        )
        raise typer.Exit(1)

    import json as _json
    from pathlib import Path

    from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

    # Load the latest snapshot if available
    snap_data: dict = {}
    if SNAPSHOTS_DIR.exists():
        snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        if snaps:
            try:
                snap_data = _json.loads(snaps[-1].read_text())
            except Exception:
                snap_data = {}

    # Gather data sections
    charge_state = (
        snap_data.get("charge_state") or snap_data.get("vehicle", {}).get("charge_state") or {}
    )
    config_data = snap_data.get("vehicle_config") or {}
    order_status = snap_data.get("order_status") or {}
    recalls = snap_data.get("nhtsa_recalls") or []
    vin_decoded = snap_data.get("vin_decode") or {}
    generated_at = snap_data.get("last_updated") or snap_data.get("timestamp") or "unknown"

    # Resolve VIN
    from tesla_cli.core.config import load_config

    cfg = load_config()
    resolved_vin = vin or snap_data.get("vin") or cfg.general.default_vin or "unknown"

    # --- Build PDF ---
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_fill_color(26, 26, 26)
    pdf.set_text_color(255, 255, 255)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, "Tesla Vehicle Dossier", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(10, 22)
    pdf.cell(0, 8, f"VIN: {resolved_vin}   |   Generated: {str(generated_at)[:19]}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)

    def section(title: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 8, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)

    def row(label: str, value: str) -> None:
        if not value or value in ("None", "none", ""):
            return
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 6, f"  {label}:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, str(value)[:80], new_x="LMARGIN", new_y="NEXT")

    # Section 1: Vehicle Identity
    section("Vehicle Identity")
    row("VIN", resolved_vin)
    row("Model", vin_decoded.get("model") or config_data.get("car_type", ""))
    row("Year", vin_decoded.get("model_year") or str(config_data.get("model_year", "")))
    row("Plant", vin_decoded.get("manufacturer") or "")
    row("Exterior Color", config_data.get("exterior_color", ""))
    row("Wheel Type", config_data.get("wheel_type", ""))
    row("Battery Type", config_data.get("battery_type", ""))
    row("Drive Unit", config_data.get("drive_unit", ""))
    pdf.ln(4)

    # Section 2: Charge State
    section("Battery & Charging")
    row("Battery Level", f"{charge_state.get('battery_level', '')}%")
    row("Battery Range", f"{charge_state.get('battery_range', '')} mi")
    row("Charge Limit", f"{charge_state.get('charge_limit_soc', '')}%")
    row("Charging State", charge_state.get("charging_state", ""))
    row("Energy Added", f"{charge_state.get('charge_energy_added', '')} kWh")
    pdf.ln(4)

    # Section 3: Order Status
    if order_status:
        section("Order & Delivery Status")
        for k, v in order_status.items():
            if v and k not in ("vin",):
                row(k.replace("_", " ").title(), str(v)[:80])
        pdf.ln(4)

    # Section 4: NHTSA Recalls
    section(f"NHTSA Recalls ({len(recalls)} found)")
    if recalls:
        for r in recalls[:10]:
            pdf.set_font("Helvetica", "B", 10)
            recall_id = r.get("NHTSACampaignNumber") or r.get("id") or ""
            pdf.cell(0, 6, f"  Recall {recall_id}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            component = r.get("Component") or r.get("component") or ""
            summary = (r.get("Summary") or r.get("consequence") or "")[:120]
            if component:
                pdf.cell(0, 5, f"    Component: {component[:80]}", new_x="LMARGIN", new_y="NEXT")
            if summary:
                pdf.multi_cell(0, 5, f"    {summary}")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, "  No open recalls found.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Section 5: Snapshot summary
    if SNAPSHOTS_DIR.exists():
        all_snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        section(f"Snapshot History ({len(all_snaps)} snapshots)")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0,
            6,
            f"  First snapshot: {all_snaps[0].stem if all_snaps else 'none'}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.cell(
            0,
            6,
            f"  Latest snapshot: {all_snaps[-1].stem if all_snaps else 'none'}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(2)

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, "Generated by tesla-cli — https://github.com/dacrypt/tesla", align="C")

    # Save
    out_path = Path(output).expanduser()
    pdf.output(str(out_path))
    console.print(f"  [green]\u2713[/green] PDF report saved to [bold]{out_path}[/bold]")


def dossier_export_html(
    output: str = typer.Option("dossier.html", "--output", "-o", help="Output HTML file path"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN or alias"),
    theme: str = typer.Option("dark", "--theme", "-t", help="CSS theme: dark (default) or light"),
) -> None:
    """Export the dossier to a standalone HTML report (no extra dependencies required).

    tesla dossier export-html
    tesla dossier export-html --theme light
    tesla dossier export-html --output ~/Desktop/my-tesla.html --theme light
    """
    import html as _html
    import json as _json
    from pathlib import Path

    from tesla_cli.core.backends.dossier import SNAPSHOTS_DIR

    # Load the latest snapshot if available
    snap_data: dict = {}
    if SNAPSHOTS_DIR.exists():
        snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        if snaps:
            try:
                snap_data = _json.loads(snaps[-1].read_text())
            except Exception:
                snap_data = {}

    # Gather data sections
    charge_state = (
        snap_data.get("charge_state") or snap_data.get("vehicle", {}).get("charge_state") or {}
    )
    config_data = snap_data.get("vehicle_config") or {}
    order_status = snap_data.get("order_status") or {}
    recalls = snap_data.get("nhtsa_recalls") or []
    vin_decoded = snap_data.get("vin_decode") or {}
    generated_at = snap_data.get("last_updated") or snap_data.get("timestamp") or "unknown"

    from tesla_cli.core.config import load_config as _lc

    cfg = _lc()
    resolved_vin = vin or snap_data.get("vin") or cfg.general.default_vin or "unknown"

    def e(v: object) -> str:
        return _html.escape(str(v)) if v else ""

    def kv_row(label: str, value: object) -> str:
        if not value or str(value) in ("None", "none", ""):
            return ""
        return f"<tr><td class='lbl'>{e(label)}</td><td>{e(value)}</td></tr>"

    # Build sections
    identity_rows = "".join(
        [
            kv_row("VIN", resolved_vin),
            kv_row("Model", vin_decoded.get("model") or config_data.get("car_type", "")),
            kv_row("Year", vin_decoded.get("model_year") or config_data.get("model_year", "")),
            kv_row("Plant", vin_decoded.get("manufacturer", "")),
            kv_row("Exterior Color", config_data.get("exterior_color", "")),
            kv_row("Wheel Type", config_data.get("wheel_type", "")),
            kv_row("Battery Type", config_data.get("battery_type", "")),
            kv_row("Drive Unit", config_data.get("drive_unit", "")),
        ]
    )

    battery_level = charge_state.get("battery_level", "")
    bar_pct = battery_level if isinstance(battery_level, (int, float)) else 0
    battery_rows = "".join(
        [
            kv_row("Battery Level", f"{battery_level}%"),
            kv_row("Battery Range", f"{charge_state.get('battery_range', '')} mi"),
            kv_row("Charge Limit", f"{charge_state.get('charge_limit_soc', '')}%"),
            kv_row("Charging State", charge_state.get("charging_state", "")),
            kv_row("Energy Added", f"{charge_state.get('charge_energy_added', '')} kWh"),
            kv_row("Charger Power", f"{charge_state.get('charger_power', '')} kW"),
        ]
    )
    battery_bar = (
        f"<div class='bar-wrap'><div class='bar' style='width:{bar_pct}%'>{bar_pct}%</div></div>"
        if bar_pct
        else ""
    )

    order_rows = ""
    if order_status:
        order_rows = "".join(
            kv_row(k.replace("_", " ").title(), v)
            for k, v in order_status.items()
            if v and k not in ("vin",)
        )

    recall_items = ""
    if recalls:
        for r in recalls[:10]:
            rid = e(r.get("NHTSACampaignNumber") or r.get("id") or "")
            comp = e(r.get("Component") or r.get("component") or "")
            summ = e((r.get("Summary") or r.get("consequence") or "")[:200])
            recall_items += (
                f"<div class='recall'>"
                f"<strong>Recall {rid}</strong>"
                + (f" — <em>{comp}</em>" if comp else "")
                + (f"<br><span class='dim'>{summ}</span>" if summ else "")
                + "</div>"
            )
    else:
        recall_items = "<p class='dim'>No open recalls found.</p>"

    snap_summary = ""
    if SNAPSHOTS_DIR.exists():
        all_snaps = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        snap_count = len(all_snaps)
        first = all_snaps[0].stem if all_snaps else "none"
        last = all_snaps[-1].stem if all_snaps else "none"
        snap_summary = (
            f"<p>{snap_count} snapshots — "
            f"first: <code>{e(first)}</code>, latest: <code>{e(last)}</code></p>"
        )

    gen_str = e(str(generated_at)[:19])
    vin_str = e(resolved_vin)

    # ── Theme CSS variables ──────────────────────────────────────────────────
    if theme.lower() == "light":
        _css_root = "--bg: #f5f5f5; --card: #ffffff; --border: #d0d0d0;\n    --text: #1a1a1a; --muted: #666; --accent: #c0001a;\n    --label: #444; --bar-bg: #e0e0e0; --bar-fg: #c0001a;"
        _h2_bg = "#f0f0f0"
        _h2_col = "#333"
        _tr_hover = "rgba(0,0,0,0.04)"
        _code_bg = "#ebebeb"
        _recall_bg = "rgba(192,0,26,0.06)"
    else:  # dark (default)
        _css_root = "--bg: #0d0d0d; --card: #1a1a1a; --border: #2e2e2e;\n    --text: #e8e8e8; --muted: #888; --accent: #e82127;\n    --label: #aaa; --bar-bg: #2e2e2e; --bar-fg: #e82127;"
        _h2_bg = "#222"
        _h2_col = "#ccc"
        _tr_hover = "rgba(255,255,255,0.03)"
        _code_bg = "#222"
        _recall_bg = "rgba(232,33,39,0.07)"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tesla Dossier — {vin_str}</title>
<style>
  :root {{
    {_css_root}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: var(--bg); color: var(--text); padding: 24px; }}
  header {{ background: var(--card); border-bottom: 3px solid var(--accent);
            padding: 24px 32px; border-radius: 8px 8px 0 0; margin-bottom: 2px; }}
  header h1 {{ font-size: 1.8rem; letter-spacing: -0.5px; }}
  header .meta {{ color: var(--muted); font-size: 0.85rem; margin-top: 6px; }}
  .section {{ background: var(--card); border: 1px solid var(--border);
              border-radius: 6px; margin: 16px 0; overflow: hidden; }}
  .section h2 {{ background: {_h2_bg}; padding: 10px 16px; font-size: 0.95rem;
                 letter-spacing: 0.5px; text-transform: uppercase; color: {_h2_col}; }}
  .section .body {{ padding: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 5px 8px; font-size: 0.9rem; }}
  td.lbl {{ color: var(--label); width: 38%; font-weight: 500; }}
  tr:hover {{ background: {_tr_hover}; }}
  .bar-wrap {{ background: var(--bar-bg); border-radius: 4px; height: 18px;
               margin: 8px 0 12px; overflow: hidden; }}
  .bar {{ background: var(--bar-fg); height: 100%; border-radius: 4px;
          font-size: 0.75rem; color: #fff; line-height: 18px; text-align: right;
          padding-right: 6px; min-width: 2rem; transition: width 0.3s; }}
  .recall {{ border-left: 3px solid var(--accent); padding: 8px 12px;
             margin-bottom: 10px; background: {_recall_bg}; border-radius: 0 4px 4px 0; }}
  .recall strong {{ font-size: 0.9rem; }}
  .dim {{ color: var(--muted); font-size: 0.85rem; }}
  code {{ background: {_code_bg}; padding: 2px 5px; border-radius: 3px; font-size: 0.82rem; }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 32px; }}
  a {{ color: var(--accent); text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>&#x1F697; Tesla Vehicle Dossier</h1>
  <div class="meta">VIN: <strong>{vin_str}</strong> &nbsp;|&nbsp; Generated: {gen_str}</div>
</header>

<div class="section">
  <h2>&#x1F4CB; Vehicle Identity</h2>
  <div class="body"><table>{identity_rows}</table></div>
</div>

<div class="section">
  <h2>&#x26A1; Battery &amp; Charging</h2>
  <div class="body">
    {battery_bar}
    <table>{battery_rows}</table>
  </div>
</div>

{'<div class="section"><h2>&#x1F4E6; Order &amp; Delivery Status</h2><div class="body"><table>' + order_rows + "</table></div></div>" if order_rows else ""}

<div class="section">
  <h2>&#x26A0;&#xFE0F; NHTSA Recalls</h2>
  <div class="body">{recall_items}</div>
</div>

<div class="section">
  <h2>&#x1F4F8; Snapshot History</h2>
  <div class="body">{snap_summary}</div>
</div>

<div class="section">
  <h2>&#x1F4CA; Data Sources</h2>
  <div class="body">
    <table>
      <tr><td class="lbl">Vehicle Identity</td><td>VIN Decode (NHTSA vPIC) + Tesla Config</td></tr>
      <tr><td class="lbl">Battery &amp; Charging</td><td>Tesla Fleet API / Owner API / TeslaMate</td></tr>
      <tr><td class="lbl">Recalls</td><td>NHTSA Government API (free, no auth)</td></tr>
      <tr><td class="lbl">Ship Tracking</td><td>shipinfo.net (web scrape)</td></tr>
      <tr><td class="lbl">Snapshots</td><td>Local archive (~/.tesla-cli/dossier/snapshots/)</td></tr>
      <tr><td class="lbl">Generated</td><td>{generated_at}</td></tr>
    </table>
  </div>
</div>

<footer>
  Generated by <a href="https://github.com/dacrypt/tesla">tesla-cli</a>
</footer>
</body>
</html>
"""

    out_path = Path(output).expanduser()
    out_path.write_text(html_content, encoding="utf-8")
    console.print(f"  [green]\u2713[/green] HTML report saved to [bold]{out_path}[/bold]")
