// Thin fetch wrapper around the FastAPI backend. All paths are relative so the
// Vite dev proxy (see vite.config.js) forwards them to :8000.

const BASE = "/api";

async function j(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(j),

  createSession: () => fetch(`${BASE}/session`, { method: "POST" }).then(j),
  getSession: (sid) => fetch(`${BASE}/session/${sid}`).then(j),
  getRequirements: (sid) => fetch(`${BASE}/session/${sid}/requirements`).then(j),
  getTemplate: (sid) => fetch(`${BASE}/session/${sid}/template`).then(j),
  listDocuments: (sid) => fetch(`${BASE}/session/${sid}/documents`).then(j),

  uploadRequirements: (sid, file, sheet) => {
    const fd = new FormData();
    fd.append("file", file);
    if (sheet) fd.append("sheet", sheet);
    return fetch(`${BASE}/session/${sid}/requirements`, { method: "POST", body: fd }).then(j);
  },
  reparseRequirements: (sid, sheet) => {
    const fd = new FormData();
    fd.append("sheet", sheet);
    return fetch(`${BASE}/session/${sid}/requirements/reparse`, { method: "POST", body: fd }).then(j);
  },
  uploadTemplate: (sid, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/session/${sid}/template`, { method: "POST", body: fd }).then(j);
  },
  loadSamples: (sid) => fetch(`${BASE}/session/${sid}/load-samples`, { method: "POST" }).then(j),

  uploadDocuments: (sid, files) => {
    const fd = new FormData();
    for (const f of files) {
      fd.append("files", f);
      fd.append("paths", f.webkitRelativePath || f.name);
    }
    return fetch(`${BASE}/session/${sid}/documents`, { method: "POST", body: fd }).then(j);
  },
  loadSampleDocuments: (sid) =>
    fetch(`${BASE}/session/${sid}/documents/load-samples`, { method: "POST" }).then(j),
  clearDocuments: (sid) =>
    fetch(`${BASE}/session/${sid}/documents`, { method: "DELETE" }).then(j),

  runMatch: (sid, useLlm) =>
    fetch(`${BASE}/session/${sid}/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_llm: useLlm }),
    }).then(j),
  getMatch: (sid) => fetch(`${BASE}/session/${sid}/match`).then(j),
  overrideMatch: (sid, ref, patch) =>
    fetch(`${BASE}/session/${sid}/match/${encodeURIComponent(ref)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(j),

  getLearning: () => fetch(`${BASE}/learning`).then(j),
  resetLearning: () => fetch(`${BASE}/learning`, { method: "DELETE" }).then(j),

  getEmail: (sid) => fetch(`${BASE}/session/${sid}/email`).then(j),
  emailDownloadUrl: (sid, fmt) => `${BASE}/session/${sid}/email/download?fmt=${fmt}`,

  getContext: (sid) => fetch(`${BASE}/session/${sid}/context`).then(j),

  _body: (o = {}) => ({
    project_name: o.projectName || null,
    period_end: o.periodEnd || null,
    developer_name: o.developerName || null,
    management_company: o.managementCompany || null,
    prepared_by: o.preparedBy || null,
  }),

  buildWorkbook(sid, opts = {}) {
    return fetch(`${BASE}/session/${sid}/workbook`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(this._body(opts)),
    }).then(j);
  },
  workbookDownloadUrl: (sid) => `${BASE}/session/${sid}/workbook/download`,

  buildRequirementsFilled(sid, opts = {}) {
    return fetch(`${BASE}/session/${sid}/requirements-filled`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(this._body(opts)),
    }).then(j);
  },
  requirementsFilledDownloadUrl: (sid) => `${BASE}/session/${sid}/requirements-filled/download`,
};
