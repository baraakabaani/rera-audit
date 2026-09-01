import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Download,
  FileSpreadsheet,
  Loader2,
  Sigma,
  TriangleAlert,
  CheckCircle2,
  ScanText,
  ListChecks,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardBody } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { SegmentedBar } from "./ui/progress";
import { RequirementsTable } from "./RequirementsTable";
import { EmailPanel } from "./EmailPanel";
import { api } from "../api";

function guessPeriodEnd(requirements) {
  const hay = `${requirements?.audit_period || ""} ${requirements?.filename || ""}`;
  const m =
    hay.match(/(\d{1,2}\s+[A-Za-z]+\s+\d{4})/) ||
    hay.match(/(\d{4})[-/](\d{2})[-/](\d{2})/);
  if (m) return m[1] || `${m[1]}`;
  const y = hay.match(/(20\d{2})/);
  return y ? `30 June ${y[1]}` : "";
}

export function Step3Review({ session, requirements, match, setMatch, learning, refreshLearning, onBack }) {
  const [report, setReport] = useState(null);
  const [reqReport, setReqReport] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [ctx, setCtx] = useState(null);
  const [projectName, setProjectName] = useState(requirements?.client_name || "");
  const [periodEnd, setPeriodEnd] = useState(() => guessPeriodEnd(requirements));
  const [developerName, setDeveloperName] = useState("");
  const [managementCompany, setManagementCompany] = useState("");
  const [preparedBy, setPreparedBy] = useState("");

  const s = match?.stats || {};
  const overrideKey = match?.rows.map((r) => r.ref + r.status).join("|");
  const opts = { projectName, periodEnd, developerName, managementCompany, preparedBy };

  // pull dates / names the backend read out of the customer files
  useEffect(() => {
    (async () => {
      try {
        const c = await api.getContext(session.id);
        setCtx(c);
        setProjectName((v) => v || c.jop_name || "");
        setPeriodEnd((v) => v || c.period_end || "");
        setDeveloperName((v) => v || c.developer_name || "");
        setManagementCompany((v) => v || c.management_company || "");
      } catch {
        /* optional */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.id]);

  const build = async () => {
    setBusy("wb");
    setError("");
    try {
      setReport(await api.buildWorkbook(session.id, opts));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const buildReq = async () => {
    setBusy("req");
    setError("");
    try {
      setReqReport(await api.buildRequirementsFilled(session.id, opts));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">Step 3 — Review & export</h2>
        <p className="text-sm text-slate-500">
          Confirm the parsed-vs-missing picture, tweak any row, then generate the workbook and email.
        </p>
      </div>

      <Card>
        <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
            <Stat label="Received" value={s.received} tone="text-emerald-600" />
            <Stat label="Partial" value={s.partial} tone="text-amber-600" />
            <Stat label="Pending" value={s.pending} tone="text-rose-600" />
            <Stat label="N/A" value={s.not_applicable} tone="text-slate-400" />
            <span className="ml-auto flex items-center gap-2 text-slate-400">
              {s.total} requirements
              {s.llm_used ? (
                <Badge tone="info">LLM reconciled</Badge>
              ) : (
                <Badge tone="neutral">deterministic</Badge>
              )}
              {s.learned_applied > 0 && (
                <Badge tone="info">{s.learned_applied} learned</Badge>
              )}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Every status change or document you attach / detach below is remembered and improves
            future matching.
            {learning?.records > 0 && (
              <>
                {" "}
                <span className="text-brand-600">
                  {learning.records} correction{learning.records === 1 ? "" : "s"} learned so far.
                </span>{" "}
                <button
                  onClick={async () => {
                    await api.resetLearning();
                    refreshLearning?.();
                  }}
                  className="underline hover:text-slate-600"
                >
                  Reset
                </button>
              </>
            )}
          </p>
          <SegmentedBar
            total={s.total}
            segments={[
              { value: s.received || 0, className: "bg-emerald-500" },
              { value: s.partial || 0, className: "bg-amber-400" },
              { value: s.pending || 0, className: "bg-rose-400" },
              { value: s.not_applicable || 0, className: "bg-slate-300" },
            ]}
          />
        </CardBody>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <RequirementsTable
            session={session}
            match={match}
            setMatch={setMatch}
            refreshLearning={refreshLearning}
          />
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-emerald-600" /> Populated workbook
              </CardTitle>
            </CardHeader>
            <CardBody className="space-y-3">
              <p className="text-sm text-slate-500">
                Fills sheets 17 &amp; 18, the financial annexures, and the Audit Report's
                13-block <strong>Procedures &amp; Findings</strong> table — formatting preserved,
                totals and cross-references as live Excel formulas, appended rows style-matched.
                Entity name and reporting period below are substituted across every sheet. With an
                LLM key, each annexure's layout is read and the findings are drafted from the
                customer files.
              </p>
              {ctx && Object.keys(ctx.sources || {}).length > 0 && (
                <p className="flex items-start gap-1.5 rounded-lg bg-brand-50 px-2.5 py-1.5 text-xs text-brand-700">
                  <ScanText className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  Read from the customer files:{" "}
                  {Object.entries(ctx.sources)
                    .map(([k, f]) => `${k.replace(/_/g, " ")} ← ${f}`)
                    .join("; ")}
                </p>
              )}
              <div className="grid gap-2 sm:grid-cols-2">
                <Field label="Entity / JOP name" value={projectName} onChange={setProjectName} placeholder="JOYA BLANCA RESIDENCES" />
                <Field label="Period end date" value={periodEnd} onChange={setPeriodEnd} placeholder="30 June 2026" />
                <Field label="Developer (name · licence · expiry)" value={developerName} onChange={setDeveloperName} placeholder="from customer files" />
                <Field label="Management company" value={managementCompany} onChange={setManagementCompany} placeholder="from customer files" />
                <Field label="Prepared by (optional)" value={preparedBy} onChange={setPreparedBy} placeholder="leave blank for a hand signature" />
              </div>
              {error && <p className="text-sm text-rose-600">{error}</p>}
              <div className="flex flex-wrap gap-2">
                <Button onClick={build} disabled={!!busy}>
                  {busy === "wb" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sigma className="h-4 w-4" />}
                  {report ? "Regenerate" : "Generate workbook"}
                </Button>
                {report && (
                  <Button variant="success" as="a" href={api.workbookDownloadUrl(session.id)}>
                    <Download className="h-4 w-4" /> Download .xlsx
                  </Button>
                )}
              </div>

              {report && (
                <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                  <p className="flex items-center gap-1.5 font-medium text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    {report.writes.length} cells written · {report.formulas_written} formulas
                  </p>
                  <p className="text-slate-500">Sheets touched: {report.sheets_touched.join(", ")}</p>
                  {report.warnings.length > 0 && (
                    <details className="text-slate-500">
                      <summary className="flex cursor-pointer items-center gap-1 text-amber-600">
                        <TriangleAlert className="h-3.5 w-3.5" />
                        {report.warnings.length} note(s) for manual review
                      </summary>
                      <ul className="mt-1 list-disc space-y-0.5 pl-5">
                        {report.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListChecks className="h-4 w-4 text-brand-600" /> Filled requirements checklist
              </CardTitle>
            </CardHeader>
            <CardBody className="space-y-3">
              <p className="text-sm text-slate-500">
                A completed copy of the original requirements workbook — STATUS and REMARKS filled
                from the match, and the audit-period banner refreshed from the customer files.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={buildReq} disabled={!!busy}>
                  {busy === "req" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ListChecks className="h-4 w-4" />}
                  {reqReport ? "Regenerate" : "Fill checklist"}
                </Button>
                {reqReport && (
                  <Button variant="success" as="a" href={api.requirementsFilledDownloadUrl(session.id)}>
                    <Download className="h-4 w-4" /> Download .xlsx
                  </Button>
                )}
              </div>
              {reqReport && (
                <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                  {reqReport.rows_written} rows filled ·{" "}
                  {Object.entries(reqReport.status_counts)
                    .map(([k, v]) => `${v} ${k}`)
                    .join(", ")}
                  {reqReport.period_updated && <> · period: {reqReport.period_updated}</>}
                </p>
              )}
            </CardBody>
          </Card>

          <EmailPanel session={session} refreshKey={overrideKey} />
        </div>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder }) {
  return (
    <label className="text-xs font-medium text-slate-500">
      {label}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-700 focus:border-brand-500 focus:outline-none"
      />
    </label>
  );
}

function Stat({ label, value, tone }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className={`text-xl font-semibold ${tone}`}>{value ?? 0}</span>
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
    </span>
  );
}
