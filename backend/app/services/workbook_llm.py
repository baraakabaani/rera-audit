"""LLM-driven annexure mapping.

For each supporting sheet the model is shown the *exact* current layout (every
non-empty cell, existing formulas, merged ranges) plus the figures extracted
from the client files, and asked to return the precise cell writes needed to
populate it - formulas for anything calculated, blanks where there is no data.

Provider-agnostic (Groq / OpenAI-compatible / Anthropic) via ``llm_client``.
Any failure is swallowed; the deterministic pass already ran.
"""
from __future__ import annotations

import time

from openpyxl.utils import get_column_letter

from ..schemas import EntityContext
from . import llm_client
from .financials import FinancialData

# deterministic code fully owns these - keep the model away from them
_SKIP = {
    "cover", "index", "audit report",
    "17. pbc checklist status", "18. requirements tracker", "16. notes summary",
}
_BATCH = 3
_MAX_LINES = 48
_DELAY_S = 2.0

_SYSTEM = (
    "You are a senior UAE RERA audit working-paper preparer. For each annexure "
    "sheet you get its EXACT current layout (every non-empty cell, with existing "
    "formulas shown verbatim) and a DATA pack of figures taken from the client's "
    "trial balance, bank statements and trade licences.\n"
    "Return the cell writes that populate the sheet the way an auditor would:\n"
    "1. Only write cells that are blank or are obvious placeholders "
    "(______, xxxx, 'Name:', <...>). NEVER overwrite an existing =formula or a "
    "row/column label.\n"
    "2. Every calculated cell MUST be an Excel formula - totals =SUM(...), "
    "differences =B5-C5, running balances =D4+B5-C5, cross-references "
    "=\'Sheet Name\'!K25. Do not paste a computed number where a formula belongs.\n"
    "3. If the DATA pack has no figure for a line, leave it blank. Never invent "
    "numbers, supplier names or dates.\n"
    "4. Values: a number, a string starting with =, or short text (a name, a "
    "date, 'Yes'/'No').\n"
    "5. Stay within the sheet's existing used rows.\n"
    'Respond ONLY as {"writes":[{"sheet":"<exact sheet name>","cell":"G17",'
    '"value":<number|string>,"note":"<why, short>"}]}'
)


def _fig(v) -> str:
    return f"{v:,.2f}" if isinstance(v, (int, float)) else "not found"


def data_pack(ctx: EntityContext, fin: FinancialData) -> str:
    buckets = [
        "income_service_charge", "income_chilled_water", "income_other",
        "exp_services", "exp_maintenance", "exp_community_improvement", "exp_utility",
        "exp_management_fee", "exp_insurance", "exp_master_community",
        "exp_reserve_fund", "exp_provision_ecl",
        "asset_sc_receivable", "asset_prepaid", "asset_deposits",
        "liab_accounts_payable", "liab_accrued", "liab_sc_advance",
    ]
    lines = [
        "ENTITY:",
        f"  JOP name: {ctx.jop_name or 'n/a'}",
        f"  Developer: {ctx.developer_name or 'n/a'}"
        + (f" | Trade Licence {ctx.developer_license}" if ctx.developer_license else "")
        + (f" | expiry {ctx.developer_license_expiry}" if ctx.developer_license_expiry else ""),
        f"  Developer address: {ctx.developer_address or 'n/a'}",
        f"  Management company: {ctx.management_company or 'n/a'}"
        + (f" | Trade Licence {ctx.management_company_license}" if ctx.management_company_license else ""),
        f"  Place: {ctx.place}",
        f"  Reporting period: {ctx.period_start} to {ctx.period_end} "
        f"(prior year end 31 December {ctx.period_end[-4:] and int(ctx.period_end[-4:]) - 1})",
        "",
        "FINANCIAL FIGURES (AED, from client files - blank means not found):",
    ]
    for b in buckets:
        lines.append(f"  {b}: {_fig(fin.total(b))}")
    lines.append(f"  bank general fund closing: {_fig(fin.bank_general_closing)}")
    lines.append(f"  bank reserve fund closing: {_fig(fin.bank_reserve_closing)}")
    if fin.suppliers:
        lines.append("  supplier balances:")
        for name, bal in fin.suppliers[:25]:
            lines.append(f"    - {name}: {bal:,.2f}")
    return "\n".join(lines)


def dump_sheet(ws) -> str:
    merged = [str(m) for m in ws.merged_cells.ranges][:24]
    head = f'### SHEET: "{ws.title}"'
    if merged:
        head += f"   (merged: {', '.join(merged)})"
    rows_out: list[str] = []
    for r in range(1, min(ws.max_row, 120) + 1):
        cells = []
        for c in range(1, min(ws.max_column, 20) + 1):
            v = ws.cell(row=r, column=c).value
            if v is None or v == "":
                continue
            s = str(v)
            if len(s) > 60:
                s = s[:60] + "…"
            cells.append(f"{get_column_letter(c)}{r}: {s}")
        if cells:
            rows_out.append("  " + "  |  ".join(cells))
        if len(rows_out) >= _MAX_LINES:
            rows_out.append("  … (rows truncated)")
            break
    return head + "\n" + "\n".join(rows_out)


def propose_writes(wb, ctx: EntityContext, fin: FinancialData) -> list[dict]:
    if not llm_client.available():
        return []
    sheets = [ws for ws in wb.worksheets if ws.title.strip().lower() not in _SKIP]
    pack = data_pack(ctx, fin)
    out: list[dict] = []

    for i in range(0, len(sheets), _BATCH):
        batch = sheets[i : i + _BATCH]
        prompt = (
            f"DATA:\n{pack}\n\n"
            "SHEETS TO POPULATE (populate every one you have data for):\n\n"
            + "\n\n".join(dump_sheet(ws) for ws in batch)
        )
        try:
            data = llm_client.chat_json(_SYSTEM, prompt, max_tokens=2600)
            for wobj in data.get("writes", []):
                if isinstance(wobj, dict) and wobj.get("sheet") and wobj.get("cell"):
                    out.append(wobj)
        except Exception as exc:  # noqa: BLE001 - keep partial results
            out.append({"__error__": f"{type(exc).__name__}: {exc}", "sheet": batch[0].title})
        if i + _BATCH < len(sheets):
            time.sleep(_DELAY_S)
    return out
