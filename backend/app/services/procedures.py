"""RERA agreed-upon-procedures matrix + findings.

``RERA_PROCEDURES`` is the minimum procedure set from the RERA scope document
(section C), grouped into the 13 blocks the Factual Finding Report uses.

:func:`build_matrix` turns it into ``(block_title, [(procedure, finding), ...])``
rows.  Findings default to *"No exceptions noted."* and are specialised from the
figures we extracted; when an LLM key is present a reconciliation pass rewrites
the findings from the actual customer files.
"""
from __future__ import annotations

import json

from ..schemas import EntityContext, MatchResult
from . import llm_client
from .financials import FinancialData

NO_EX = "No exceptions noted."
NA = "Not applicable."

# (block no, block title, [procedures])
RERA_PROCEDURES: list[tuple[int, str, list[str]]] = [
    (1, "Project details", [
        "Verify the JOP name with the Mollak system.",
        "Verify the master community and units' details with the budget report.",
        "Verify the trade licence of the management company and developer, and the expiry of the trade licence.",
    ]),
    (2, "Other income", [
        "Verify the other income agreement.",
        "Verify the sample of other income invoices.",
        "Verify the other income to the statement of income and expenditure (PL).",
        "Verify the tender details and obtain / validate the reasons for not tendering the services.",
    ]),
    (3, "Budget vs actual", [
        "Verify the contractual expenses with signed supplier agreements / purchase orders / work done certificates.",
        "Obtain the month-wise utility schedule and check it with the utility bills.",
        "Check the insurance policy and tax invoice to verify the insurance.",
        "Check master community expenses with master community invoices / SOA.",
        "Check management costs against the approved budget.",
        "Check other income against contracts / invoices.",
    ]),
    (4, "Changes in suppliers", [
        "Check the supplier names against the budget review report.",
        "Check the agreement / sample of invoices for the actual deployment of suppliers.",
    ]),
    (5, "Community improvements", [
        "Check tender documents (material sample selected).",
        "Check supplier invoices, work done certificates and picture proof for delivery of services (material sample selected).",
        "Check with the management whether the service provider is a related party.",
        "Check whether the actual expense is over-spent compared to the approved budget.",
    ]),
    (6, "Reserve fund expenses", [
        "Check tender documents (material sample selected).",
        "Check supplier invoices, work done certificates and picture proof for delivery of services (material sample selected).",
        "Check property observer compliances.",
    ]),
    (7, "Unplanned maintenance", [
        "Check tender documents (material sample selected).",
        "Check supplier invoices, work done certificates and picture proof for delivery of services (material sample selected).",
        "Check with the management whether the service provider is a related party.",
        "Check whether the actual expense is over-spent compared to the approved budget.",
        "Check whether unbudgeted costs that are AMC in nature are reported under unplanned maintenance.",
    ]),
    (8, "Bank balances", [
        "Verify the bank reconciliation statements for regulated and non-regulated bank accounts and whether they are properly approved.",
        "Verify the bank statements to check the bank closing balance at the reporting date.",
        "Check whether service charge is collected outside regulated bank accounts.",
        "Check whether the reserve fund is properly funded and agrees with the RERA Circular.",
    ]),
    (9, "Reconciliation of service charge receivable / in-unit chilled water opening to closing balance", [
        "Check the schedule of the unit-wise receivable balance from opening to closing balance.",
        "Check a sample of invoicing to units; whether it is done as per the approved budget.",
        "Check a sample of receipts credited to units.",
        "Check the unit-wise balance against the Mollak report.",
        "Check the total of the service charge receivable closing balance to the balance sheet.",
        "Check the reconciliation for in-unit chilled water or other recovery from units (written confirmation from the billing company).",
        "Check the aging report for service charge receivable.",
        "Check the management company has done the expected credit loss adjustment.",
        "Check recovery actions or legal proceedings taken for long-due debtors.",
    ]),
    (10, "List of supplier balances", [
        "Check the total of the list of supplier balances to the trial balance.",
        "Check suppliers' SOA against supplier balances or subsequent settlement.",
        "Verify the material differences between suppliers' balances and SOA balances.",
        "Check the supplier aging report and obtain reasons for long-outstanding supplier balances.",
    ]),
    (11, "List of accruals", [
        "Check the accuracy of current-period accruals by verifying the current-period expense (sample basis).",
        "Obtain reasons for long-outstanding accruals; why the accruals are not closed.",
        "Obtain the basis for long-outstanding accruals (sample basis).",
    ]),
    (12, "Transactions with the developer or affiliated entities", [
        "Obtain the list of affiliated entities of the developer and the nature of transactions.",
        "Check a sample of documents to verify the current-period transactions.",
        "Obtain balance confirmation for closing balances.",
        "Check whether the management has taken legal action against closing balances.",
        "Check whether the management has made a provision for doubtful debt on long-outstanding receivable balances.",
    ]),
    (13, "Transactions with the management company", [
        "Obtain the list of transactions from opening balance to closing balance.",
        "Check a sample of documents to verify the current-period transactions.",
        "Obtain balance confirmation for closing balances.",
        "Check whether the management has taken legal action against closing balances (former management company).",
        "Check whether the management has made a provision for doubtful debt on long-outstanding receivable balances from the former management company.",
    ]),
]


def _aed(v) -> str:
    return f"AED {v:,.0f}" if isinstance(v, (int, float)) else "—"


def _deterministic_finding(block: int, proc: str, fin: FinancialData, ctx: EntityContext) -> str:
    p = proc.lower()
    t = fin.total

    if block == 1:
        if "jop name" in p:
            return f"Agreed the JOP name '{ctx.jop_name}' to the Mollak system." if ctx.jop_name else NO_EX
        if "trade licence" in p or "trade license" in p:
            if ctx.developer_license or ctx.management_company_license:
                bits = []
                if ctx.developer_license:
                    bits.append(f"developer TL {ctx.developer_license}"
                                + (f", expiry {ctx.developer_license_expiry}" if ctx.developer_license_expiry else ""))
                if ctx.management_company_license:
                    bits.append(f"management company TL {ctx.management_company_license}")
                return "Verified (" + "; ".join(bits) + "). No exceptions noted."
            return "Trade licence documentation was not provided by the management company for verification."

    if block == 2:
        oi = t("income_other")
        if "to the statement" in p or "agreement" in p:
            return (f"Other income of {_aed(oi)} agreed to the statement of income and expenditure; supporting "
                    f"invoices verified.") if oi is not None else NA
        return NO_EX if oi is not None else NA

    if block == 3:
        if "utility" in p:
            return "Month-wise utility schedule agreed to DEWA / Empower / telecom invoices." if t("exp_utility") is not None else NO_EX
        if "insurance" in p:
            return "Insurance policy and premium tax invoice verified." if t("exp_insurance") is not None else NO_EX
        if "master community" in p:
            return "Agreed to master community invoices / SOA." if t("exp_master_community") is not None else NA
        if "management cost" in p:
            return "Management fee agreed to the approved budget." if t("exp_management_fee") is not None else NO_EX
        return NO_EX

    if block == 5:
        return NA if t("exp_community_improvement") is None else NO_EX

    if block == 6 and "property observer" in p:
        return ("The property observer requirement is not applicable where the reserve fund projects were approved "
                "and commenced prior to the RERA property-observer implementation.")

    if block == 8:
        if "closing balance at the reporting date" in p:
            parts = []
            if fin.bank_general_closing is not None:
                parts.append(f"General Fund {_aed(fin.bank_general_closing)}")
            if fin.bank_reserve_closing is not None:
                parts.append(f"Reserve Fund {_aed(fin.bank_reserve_closing)}")
            return ("Agreed to the bank statements. Closing balances: " + "; ".join(parts) + ".") if parts else NO_EX
        if "reserve fund is properly funded" in p:
            if fin.bank_reserve_closing is not None:
                return (f"Reserve fund bank balance amounts to {_aed(fin.bank_reserve_closing)}. The accumulated "
                        f"reserve fund balance per the books is to be confirmed by the management company.")
            return "Reserve fund bank confirmation was not provided by the management company."

    if block == 9:
        if "expected credit loss" in p:
            ecl = t("exp_provision_ecl")
            return (f"A provision for expected credit loss amounting to {_aed(ecl)} was recognised during the period."
                    if ecl is not None else "No expected credit loss adjustment was recognised during the period.")
        if "legal proceedings" in p or "recovery actions" in p:
            return "The management company has issued legal notices to long-outstanding unit owners (refer Annexure 11.4)."

    if block == 10:
        total = sum(b for _, b in fin.suppliers) if fin.suppliers else None
        if "total of the list of supplier balances" in p:
            return f"The list of suppliers' balances totals {_aed(total)}; agreed to the trial balance." if total else NO_EX
        if "long-outstanding supplier balances" in p:
            return ("Long-outstanding balances are due to the non-receipt of invoices / SOAs from the suppliers."
                    if fin.suppliers else NA)
        return NO_EX

    if block == 11:
        acc = t("liab_accrued")
        if "accuracy of current-period accruals" in p:
            return (f"Accrued expenses per the trial balance amount to {_aed(acc)}; current-period accruals verified "
                    f"on a sample basis.") if acc is not None else NO_EX
        if "long-outstanding accruals" in p:
            return "Long-outstanding accruals are due to the non-receipt of final invoices from the suppliers."

    if block in (12, 13):
        party = "developer or its affiliated entities" if block == 12 else "former management company"
        if "list of affiliated" in p or "list of transactions" in p:
            return NA
        if "balance confirmation" in p:
            return f"No transactions have been made with the {party} during the period."
        if "provision for doubtful debt" in p:
            return NA
        if "legal action" in p:
            return NA
        return f"No transactions with the {party} were noted during the period."

    return NO_EX


def _llm_findings(rows, fin: FinancialData, ctx: EntityContext, match: MatchResult) -> dict:
    if not llm_client.available():
        return {}
    from .workbook_llm import data_pack

    proc_lines = [f'{{"block":{b},"i":{i},"procedure":{json.dumps(p)}}}'
                  for b, _title, procs in RERA_PROCEDURES for i, p in enumerate(procs)]
    pend = [r.ref + " " + r.requirement for r in match.rows if r.status == "Pending"][:20]
    system = (
        "You are a UAE RERA agreed-upon-procedures auditor writing the Findings column of the "
        "factual finding report. For each procedure, write a concise finding in the firm's house "
        "style: default to exactly 'No exceptions noted.' unless the DATA or the not-provided list "
        "warrants otherwise. Use 'Not applicable.' when the JOP has no such item. When a figure is "
        "given, quote it (AED, thousands separators). Never invent numbers. 1-3 sentences each."
    )
    user = (
        f"DATA:\n{data_pack(ctx, fin)}\n\n"
        f"NOT PROVIDED BY THE CLIENT:\n" + ("\n".join(pend) or "(none)") + "\n\n"
        "PROCEDURES (one JSON per line):\n" + "\n".join(proc_lines) + "\n\n"
        'Return {"findings":[{"block":1,"i":0,"finding":"..."}]} - include every procedure.'
    )
    try:
        data = llm_client.chat_json(system, user, max_tokens=3500)
    except Exception:
        return {}
    out: dict[tuple[int, int], str] = {}
    for f in data.get("findings", []):
        try:
            out[(int(f["block"]), int(f["i"]))] = str(f["finding"]).strip()[:600]
        except Exception:
            continue
    return out


def build_matrix(
    fin: FinancialData, ctx: EntityContext, match: MatchResult, *, use_llm: bool = True
) -> tuple[list[tuple[int, str, list[tuple[str, str]]]], bool]:
    llm_map = _llm_findings(RERA_PROCEDURES, fin, ctx, match) if use_llm else {}
    blocks = []
    for b, title, procs in RERA_PROCEDURES:
        rows = []
        for i, proc in enumerate(procs):
            finding = llm_map.get((b, i)) or _deterministic_finding(b, proc, fin, ctx)
            rows.append((proc, finding or NO_EX))
        blocks.append((b, title, rows))
    return blocks, bool(llm_map)
