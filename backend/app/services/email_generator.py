"""Build the client follow-up email from the match result."""
from __future__ import annotations

from datetime import date
from email.message import EmailMessage
from html import escape

from ..schemas import EmailDraft, MatchResult, RequirementsResult

_SIGNOFF = [
    "Kind regards,",
    "",
    "Audit Team",
    "Parker Russell Obaid Auditing",
    "Member of Parker Russell International",
    "Dubai, United Arab Emirates",
]


def _groups(match: MatchResult):
    received, pending, comments = [], [], []
    for r in match.rows:
        files = ", ".join(m.filename for m in r.matched_files) or "-"
        if r.status == "Received":
            received.append((r.ref, r.requirement, files))
        elif r.status == "Not applicable":
            continue
        elif r.status == "Partial":
            comments.append((r.ref, r.requirement, r.comment or "Document provided appears incomplete - please confirm / resend."))
        else:
            pending.append((r.ref, r.requirement, r.evidence_type))
        if r.status != "Partial" and r.comment:
            comments.append((r.ref, r.requirement, r.comment))
    return received, pending, comments


def build_email(match: MatchResult, requirements: RequirementsResult | None) -> EmailDraft:
    client = (requirements.client_name if requirements else "") or "Client"
    period = (requirements.audit_period if requirements else "") or "the interim period"
    today = date.today().strftime("%d %B %Y")
    received, pending, comments = _groups(match)

    subject = f"RERA Interim Audit - Outstanding Documents ({client})".strip()

    # ---- plain text -------------------------------------------------------
    L: list[str] = []
    L.append(f"Date: {today}")
    L.append("")
    L.append(f"Dear {client},")
    L.append("")
    L.append(
        f"Thank you for the documents provided to date in connection with the RERA "
        f"interim audit for {period}. Following our review, we set out below the "
        f"current status of the requested information."
    )
    L.append("")
    L.append(f"1. RECEIVED & VERIFIED ({len(received)})")
    L.append("-" * 48)
    if received:
        for ref, req, files in received:
            L.append(f"  [{ref}] {req}")
            L.append(f"        mapped file(s): {files}")
    else:
        L.append("  (none yet)")
    L.append("")
    L.append(f"2. PENDING / MISSING ({len(pending)})")
    L.append("-" * 48)
    if pending:
        for ref, req, ev in pending:
            L.append(f"  [{ref}] {req}")
            if ev:
                L.append(f"        required evidence: {ev}")
    else:
        L.append("  (none outstanding)")
    L.append("")
    if comments:
        L.append(f"3. COMMENTS / CLARIFICATIONS ({len(comments)})")
        L.append("-" * 48)
        for ref, req, note in comments:
            L.append(f"  [{ref}] {req}")
            L.append(f"        {note}")
        L.append("")
    L.append(
        "We would be grateful to receive the pending items, and your responses to "
        "the clarifications above, at your earliest convenience so that we can "
        "progress the audit without delay."
    )
    L.append("")
    L.extend(_SIGNOFF)
    body_text = "\n".join(L)

    # ---- html -----------------------------------------------------------
    def _ul(items, render):
        if not items:
            return "<p style='color:#64748b'>(none)</p>"
        return "<ul>" + "".join(f"<li>{render(x)}</li>" for x in items) + "</ul>"

    html = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#0f172a;line-height:1.55">
  <p>Date: {escape(today)}</p>
  <p>Dear {escape(client)},</p>
  <p>Thank you for the documents provided to date in connection with the RERA interim
     audit for {escape(period)}. Following our review, we set out below the current
     status of the requested information.</p>

  <h3 style="color:#047857;margin-bottom:4px">1. Received &amp; Verified ({len(received)})</h3>
  {_ul(received, lambda x: f"<b>[{escape(x[0])}]</b> {escape(x[1])}<br><span style='color:#475569'>mapped file(s): {escape(x[2])}</span>")}

  <h3 style="color:#b45309;margin-bottom:4px">2. Pending / Missing ({len(pending)})</h3>
  {_ul(pending, lambda x: f"<b>[{escape(x[0])}]</b> {escape(x[1])}" + (f"<br><span style='color:#475569'>required evidence: {escape(x[2])}</span>" if x[2] else ""))}

  {"".join([
     f"<h3 style='color:#1d4ed8;margin-bottom:4px'>3. Comments / Clarifications ({len(comments)})</h3>",
     _ul(comments, lambda x: f"<b>[{escape(x[0])}]</b> {escape(x[1])}<br><span style='color:#475569'>{escape(x[2])}</span>"),
   ]) if comments else ""}

  <p>We would be grateful to receive the pending items, and your responses to the
     clarifications above, at your earliest convenience so that we can progress the
     audit without delay.</p>
  <p>{"<br>".join(escape(s) for s in _SIGNOFF)}</p>
</div>"""

    return EmailDraft(subject=subject, to="", body_text=body_text, body_html=html)


def to_eml(draft: EmailDraft) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = draft.subject
    if draft.to:
        msg["To"] = draft.to
    msg.set_content(draft.body_text)
    msg.add_alternative(draft.body_html, subtype="html")
    return bytes(msg)
