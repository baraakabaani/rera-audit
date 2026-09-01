import { Fragment, useMemo, useState } from "react";
import { ChevronRight, Paperclip, Bot, Pencil, Brain } from "lucide-react";
import { Badge } from "./ui/badge";
import { cn } from "../lib/utils";
import { api } from "../api";

const STATUSES = ["Received", "Partial", "Pending", "Not applicable"];

export function RequirementsTable({ session, match, setMatch, refreshLearning }) {
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);

  const rows = useMemo(() => {
    if (!match) return [];
    if (filter === "all") return match.rows;
    return match.rows.filter((r) => r.status === filter);
  }, [match, filter]);

  const counts = match?.stats || {};

  const setStatus = async (ref, status) => {
    const updated = await api.overrideMatch(session.id, ref, { status });
    setMatch(updated);
    refreshLearning?.();
  };

  const detach = async (ref, docId) => {
    const updated = await api.overrideMatch(session.id, ref, { remove_doc_ids: [docId] });
    setMatch(updated);
    refreshLearning?.();
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>
          All {match?.rows.length ?? 0}
        </FilterChip>
        <FilterChip active={filter === "Received"} tone="Received" onClick={() => setFilter("Received")}>
          Received {counts.received ?? 0}
        </FilterChip>
        <FilterChip active={filter === "Partial"} tone="Partial" onClick={() => setFilter("Partial")}>
          Partial {counts.partial ?? 0}
        </FilterChip>
        <FilterChip active={filter === "Pending"} tone="Pending" onClick={() => setFilter("Pending")}>
          Pending {counts.pending ?? 0}
        </FilterChip>
        <FilterChip
          active={filter === "Not applicable"}
          tone="Not applicable"
          onClick={() => setFilter("Not applicable")}
        >
          N/A {counts.not_applicable ?? 0}
        </FilterChip>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 scroll-thin">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="w-16 py-2.5 pl-4 font-medium">Ref</th>
              <th className="py-2.5 pr-3 font-medium">Requirement</th>
              <th className="w-32 py-2.5 pr-3 font-medium">Status</th>
              <th className="w-40 py-2.5 pr-3 font-medium">Matched files</th>
              <th className="w-8 py-2.5 pr-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => {
              const isOpen = open === r.ref;
              return (
                <Fragment key={r.ref}>
                  <tr
                    className={cn("cursor-pointer hover:bg-slate-50", isOpen && "bg-slate-50")}
                    onClick={() => setOpen(isOpen ? null : r.ref)}
                  >
                    <td className="py-2.5 pl-4 align-top font-mono text-xs text-slate-500">{r.ref}</td>
                    <td className="py-2.5 pr-3 align-top">
                      <p className="text-slate-700">{r.requirement}</p>
                      <p className="text-xs text-slate-400">{r.section_title}</p>
                    </td>
                    <td className="py-2.5 pr-3 align-top">
                      <Badge tone={r.status}>{r.status}</Badge>
                      {r.overridden && (
                        <span title="Manually overridden">
                          <Pencil className="ml-1 inline h-3 w-3 text-slate-400" />
                        </span>
                      )}
                      {r.learned_note && (
                        <span title={`Learned: ${r.learned_note}`}>
                          <Brain className="ml-1 inline h-3.5 w-3.5 text-brand-500" />
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pr-3 align-top">
                      {r.matched_files.length ? (
                        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                          <Paperclip className="h-3.5 w-3.5" />
                          {r.matched_files.length}
                          {r.llm_rationale && <Bot className="h-3.5 w-3.5 text-brand-500" />}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-300">—</span>
                      )}
                    </td>
                    <td className="py-2.5 pr-3 align-top text-slate-300">
                      <ChevronRight
                        className={cn("h-4 w-4 transition-transform", isOpen && "rotate-90")}
                      />
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="bg-slate-50">
                      <td />
                      <td colSpan={4} className="px-3 pb-4 pt-1">
                        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
                          {r.evidence_type && (
                            <p className="text-xs text-slate-500">
                              <span className="font-medium text-slate-600">Evidence required:</span>{" "}
                              {r.evidence_type}
                            </p>
                          )}
                          {r.comment && (
                            <p className="text-xs text-amber-700">{r.comment}</p>
                          )}
                          {r.llm_rationale && (
                            <p className="flex items-start gap-1.5 text-xs text-brand-700">
                              <Bot className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {r.llm_rationale}
                            </p>
                          )}
                          {r.learned_note && (
                            <p className="flex items-start gap-1.5 text-xs text-brand-700">
                              <Brain className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {r.learned_note}
                            </p>
                          )}
                          <div>
                            <p className="mb-1 text-xs font-medium text-slate-500">Mapped documents</p>
                            {r.matched_files.length ? (
                              <ul className="space-y-1">
                                {r.matched_files.map((m) => (
                                  <li
                                    key={m.doc_id}
                                    className="flex items-center gap-2 text-xs text-slate-600"
                                  >
                                    <Paperclip className="h-3 w-3 shrink-0 text-slate-400" />
                                    <span className="truncate">{m.filename}</span>
                                    <Badge tone={m.method === "learned" ? "info" : "neutral"}>
                                      {m.method}
                                    </Badge>
                                    <span className="text-slate-400">score {m.score}</span>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        detach(r.ref, m.doc_id);
                                      }}
                                      className="ml-auto rounded px-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                                      title="Remove this document — the matcher learns from it"
                                    >
                                      ✕
                                    </button>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-xs text-slate-400">No documents mapped.</p>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-1.5 pt-1">
                            <span className="text-xs text-slate-400">Override status:</span>
                            {STATUSES.map((s) => (
                              <button
                                key={s}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setStatus(r.ref, s);
                                }}
                                className={cn(
                                  "rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset transition",
                                  r.status === s
                                    ? "bg-brand-600 text-white ring-brand-600"
                                    : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-100"
                                )}
                              >
                                {s}
                              </button>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-slate-400">
                  No requirements in this view.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilterChip({ active, tone, children, onClick }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition",
        active
          ? "bg-slate-800 text-white ring-slate-800"
          : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-100"
      )}
    >
      {children}
    </button>
  );
}
