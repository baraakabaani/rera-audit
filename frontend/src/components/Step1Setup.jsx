import { useState } from "react";
import { FileSpreadsheet, CheckCircle2, Sparkles, ArrowRight } from "lucide-react";
import { Card, CardHeader, CardTitle, CardBody } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Dropzone } from "./ui/dropzone";
import { api } from "../api";

function FileSlot({ label, description, done, meta, onPick, busy }) {
  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>{label}</CardTitle>
        {done && (
          <Badge tone="Received">
            <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Loaded
          </Badge>
        )}
      </CardHeader>
      <CardBody className="space-y-3">
        <p className="text-sm text-slate-500">{description}</p>
        {done ? (
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <FileSpreadsheet className="h-5 w-5 text-emerald-600" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-700">{meta?.name}</p>
              <p className="text-xs text-slate-500">{meta?.sub}</p>
            </div>
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => onPick(null)}>
              Replace
            </Button>
          </div>
        ) : (
          <Dropzone
            accept=".xlsx,.xlsm"
            title="Drop the .xlsx file"
            hint={busy ? "Uploading…" : "or click to browse"}
            onFiles={(files) => onPick(files[0])}
          />
        )}
      </CardBody>
    </Card>
  );
}

export function Step1Setup({ session, requirements, template, setRequirements, setTemplate, onNext }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const pickRequirements = async (file) => {
    setError("");
    if (!file) return setRequirements(null);
    setBusy("req");
    try {
      setRequirements(await api.uploadRequirements(session.id, file));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const pickTemplate = async (file) => {
    setError("");
    if (!file) return setTemplate(null);
    setBusy("tmpl");
    try {
      setTemplate(await api.uploadTemplate(session.id, file));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const loadSamples = async () => {
    setError("");
    setBusy("samples");
    try {
      await api.loadSamples(session.id);
      setRequirements(await api.getRequirements(session.id));
      setTemplate(await api.getTemplate(session.id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Step 1 — Auditor inputs</h2>
          <p className="text-sm text-slate-500">
            Upload the RERA requirements checklist and the master working-paper template.
          </p>
        </div>
        <Button variant="subtle" size="sm" onClick={loadSamples} disabled={!!busy}>
          <Sparkles className="h-4 w-4" />
          {busy === "samples" ? "Loading samples…" : "Load bundled samples"}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        <FileSlot
          label="Requirements Checklist"
          description="Excel checklist of documents requested from the client (e.g. OA_DLD_RERA_Interim Audit_Requirements…xlsx)."
          done={!!requirements && !requirements._pending}
          busy={busy === "req"}
          meta={{
            name: requirements?.filename,
            sub: requirements
              ? `${requirements.items?.length || 0} line items · ${
                  Object.keys(requirements.section_titles || {}).length
                } sections`
              : "",
          }}
          onPick={pickRequirements}
        />
        <FileSlot
          label="Master Template"
          description="The working-paper template workbook to be populated (template.xlsx)."
          done={!!template}
          busy={busy === "tmpl"}
          meta={{
            name: template?.filename,
            sub: template ? `${template.sheets?.length || 0} sheets` : "",
          }}
          onPick={pickTemplate}
        />
      </div>

      {requirements && !requirements._pending && (
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>
              Parsed requirements preview
              <span className="ml-2 text-xs font-normal text-slate-400">
                {requirements.items?.length || 0} items ·{" "}
                {Object.keys(requirements.section_titles || {}).length} sections
              </span>
            </CardTitle>
            {(requirements.available_sheets?.length || 0) > 1 && (
              <label className="flex items-center gap-2 text-xs text-slate-500">
                Worksheet
                <select
                  value={requirements.sheet}
                  disabled={busy === "sheet"}
                  onChange={async (e) => {
                    setBusy("sheet");
                    setError("");
                    try {
                      setRequirements(await api.reparseRequirements(session.id, e.target.value));
                    } catch (err) {
                      setError(err.message);
                    } finally {
                      setBusy("");
                    }
                  }}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-700"
                >
                  {requirements.available_sheets.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </CardHeader>
          <CardBody className="max-h-64 overflow-auto scroll-thin">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white text-left text-xs uppercase text-slate-400">
                <tr>
                  <th className="py-1 pr-3 font-medium">Ref</th>
                  <th className="py-1 pr-3 font-medium">Requirement</th>
                  <th className="py-1 pr-3 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(requirements.items || []).map((it) => (
                  <tr key={it.ref}>
                    <td className="py-1.5 pr-3 font-mono text-xs text-slate-500">{it.ref}</td>
                    <td className="py-1.5 pr-3 text-slate-700">{it.requirement}</td>
                    <td className="py-1.5 pr-3 text-slate-400">{it.evidence_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      <div className="flex justify-end">
        <Button onClick={onNext} disabled={!requirements || requirements._pending || !template}>
          Continue <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
