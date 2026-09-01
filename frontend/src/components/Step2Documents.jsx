import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  FileSpreadsheet,
  FileWarning,
  Folder,
  Loader2,
  Sparkles,
  Trash2,
  Play,
  Brain,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardBody } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Dropzone } from "./ui/dropzone";
import { fmtBytes } from "../lib/utils";
import { api } from "../api";

const ICONS = { ".pdf": FileText, ".docx": FileText, ".xlsx": FileSpreadsheet, ".xls": FileSpreadsheet, ".csv": FileSpreadsheet };

const SUPPORTED = [".pdf", ".docx", ".xlsx", ".xls", ".csv"];
const IGNORE = /(^|\/)(\.|~\$|node_modules\/|thumbs\.db$|desktop\.ini$)/i;
const BATCH = 12;

export function Step2Documents({ session, documents, setDocuments, setMatch, llmAvailable, llmProvider, learning, onBack, onNext }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [useLlm, setUseLlm] = useState(true);
  const [progress, setProgress] = useState(null); // { done, total }

  const grouped = useMemo(() => {
    const g = {};
    for (const d of documents) (g[d.folder || "(root)"] ||= []).push(d);
    return g;
  }, [documents]);

  const errors = documents.filter((d) => d.error).length;

  const addFiles = async (picked) => {
    setError("");
    const files = picked.filter((f) => {
      const rel = f.webkitRelativePath || f.name;
      const ext = rel.slice(rel.lastIndexOf(".")).toLowerCase();
      return SUPPORTED.includes(ext) && !IGNORE.test(rel);
    });
    const skipped = picked.length - files.length;
    if (!files.length) {
      setError(
        skipped
          ? `None of the ${skipped} selected item(s) are supported (PDF / DOCX / XLSX / XLS / CSV).`
          : "No files selected."
      );
      return;
    }

    setBusy("upload");
    setProgress({ done: 0, total: files.length });
    try {
      for (let i = 0; i < files.length; i += BATCH) {
        const chunk = files.slice(i, i + BATCH);
        const added = await api.uploadDocuments(session.id, chunk);
        setDocuments((prev) => [...prev, ...added]);
        setProgress({ done: Math.min(i + BATCH, files.length), total: files.length });
      }
      setMatch(null);
      if (skipped) setError(`Uploaded ${files.length} file(s); skipped ${skipped} unsupported item(s).`);
    } catch (e) {
      setError(`Upload failed after ${progress?.done || 0} file(s): ${e.message}`);
    } finally {
      setBusy("");
      setProgress(null);
    }
  };

  const loadSamples = async () => {
    setError("");
    setBusy("samples");
    try {
      const added = await api.loadSampleDocuments(session.id);
      setDocuments(added);
      setMatch(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const clearAll = async () => {
    await api.clearDocuments(session.id);
    setDocuments([]);
    setMatch(null);
  };

  const runMatcher = async () => {
    setError("");
    setBusy("match");
    try {
      const result = await api.runMatch(session.id, useLlm && llmAvailable);
      setMatch(result);
      onNext();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">Step 2 — Customer documents</h2>
        <p className="text-sm text-slate-500">
          Drag in individual files or whole section folders. Supported: PDF, DOCX, XLSX, XLS, CSV.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          {error}
        </div>
      )}

      <Dropzone busy={busy === "upload"} onFiles={addFiles} />

      {progress && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-slate-500">
            <span>Uploading & extracting…</span>
            <span>
              {progress.done} / {progress.total}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full bg-brand-500 transition-all"
              style={{ width: `${(progress.done / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="subtle" size="sm" onClick={loadSamples} disabled={!!busy}>
          <Sparkles className="h-4 w-4" />
          {busy === "samples" ? "Loading…" : "Load bundled sample documents"}
        </Button>
        {documents.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearAll} disabled={!!busy}>
            <Trash2 className="h-4 w-4" /> Clear all
          </Button>
        )}
        <div className="ml-auto flex items-center gap-4 text-sm text-slate-500">
          <span>
            <b className="text-slate-800">{documents.length}</b> files
          </span>
          {errors > 0 && (
            <span className="flex items-center gap-1 text-amber-600">
              <FileWarning className="h-4 w-4" /> {errors} unreadable
            </span>
          )}
        </div>
      </div>

      {documents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Ingested documents</CardTitle>
          </CardHeader>
          <CardBody className="max-h-80 space-y-4 overflow-auto scroll-thin">
            {Object.entries(grouped).map(([folder, docs]) => (
              <div key={folder}>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <Folder className="h-3.5 w-3.5" /> {folder}
                </div>
                <ul className="divide-y divide-slate-100">
                  {docs.map((d) => {
                    const Icon = ICONS[d.ext] || FileText;
                    return (
                      <li key={d.id} className="flex items-center gap-3 py-1.5">
                        <Icon className="h-4 w-4 shrink-0 text-slate-400" />
                        <span className="min-w-0 flex-1 truncate text-sm text-slate-700">
                          {d.filename}
                        </span>
                        {d.error ? (
                          <Badge tone="Pending">unreadable</Badge>
                        ) : (
                          <span className="text-xs text-slate-400">
                            {d.page_count ? `${d.page_count}p · ` : ""}
                            {d.char_count.toLocaleString()} chars · {fmtBytes(d.size_bytes)}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      <Card>
        <CardBody className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1.5">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300"
                checked={useLlm && llmAvailable}
                disabled={!llmAvailable}
                onChange={(e) => setUseLlm(e.target.checked)}
              />
              <span className="flex items-center gap-1">
                LLM assist (matching + workbook mapping)
                {llmAvailable ? (
                  <Badge tone="info">{llmProvider || "available"}</Badge>
                ) : (
                  <Badge tone="neutral">no API key — deterministic only</Badge>
                )}
              </span>
            </label>
            {learning?.records > 0 && (
              <p className="flex items-center gap-1.5 text-xs text-brand-700">
                <Brain className="h-3.5 w-3.5" />
                Learning from {learning.records} past correction
                {learning.records === 1 ? "" : "s"} ({learning.confirmations} confirmed,{" "}
                {learning.rejections} rejected, {learning.status_edits} status)
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onBack}>
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <Button onClick={runMatcher} disabled={documents.length === 0 || !!busy}>
              {busy === "match" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run audit matcher <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
