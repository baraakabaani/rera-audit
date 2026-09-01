# RERA Audit Automation

Full-stack tool that automates the interim/annual RERA audit intake:

1. **Ingest** the auditor's *Requirements Checklist* and *Master Template* workbooks.
2. **Extract & classify** customer documents (PDF / DOCX / XLSX / XLS / CSV) and
   match them against the checklist line items — deterministic keyword scoring
   plus an optional Anthropic LLM reconciliation pass.
3. **Detect missing items** and draft a formatted client follow-up email
   (copy to clipboard / download `.eml` / `.txt`).
4. **Generate a populated copy of the template** — formatting, fonts, fills and
   merged cells preserved; every calculated total written as a **live Excel
   formula** (`=SUM(...)`, `=K57-K31`, `=COUNTIF(...)`).

```
rera site/
├── backend/         FastAPI + openpyxl + pandas + pdfplumber + python-docx
│   └── app/
│       ├── main.py              app + CORS + routers
│       ├── config.py            env-driven settings
│       ├── schemas.py           Pydantic models
│       ├── store.py             in-memory session store (files on disk)
│       ├── routers/             sessions · documents · outputs
│       └── services/
│           ├── requirements_parser.py   checklist  -> line items
│           ├── document_extractor.py    file       -> text + metadata
│           ├── matcher.py               line items x docs -> status
│           ├── feedback.py              learns from auditor corrections
│           ├── llm_client.py            one entry point: Groq / OpenAI / Anthropic
│           ├── llm.py                   match reconciliation pass
│           ├── workbook_llm.py          "understand each sheet, write the cells" pass
│           ├── financials.py            trial balance / bank stmt -> figures
│           ├── email_generator.py       match result -> email + .eml
│           └── workbook_generator.py    template + data -> populated .xlsx
└── frontend/        React (Vite) + Tailwind + lucide-react — 3-step wizard
```

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on *nix)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: <http://localhost:8000/docs>

**Optional LLM** — powers (a) match reconciliation and (b) an *"read each
annexure's layout, write the exact cells"* workbook-mapping pass. Set **one**
credential (auto-detected):

```bash
set GROQ_API_KEY=gsk_...                # FREE — console.groq.com  (default: llama-3.3-70b-versatile)
set OPENAI_API_KEY=sk-...               # OpenAI, or any OpenAI-compatible endpoint via OPENAI_BASE_URL
set ANTHROPIC_API_KEY=sk-ant-...        # Claude, or run `ant auth login`
```

`LLM_PROVIDER` (`auto`|`groq`|`openai`|`anthropic`|`off`) and `LLM_MODEL` override
detection; `LLM_WORKBOOK=false` disables just the workbook pass. Without any key
everything runs offline on deterministic logic.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173  (proxies /api -> :8000)
```

## Using it

| Step | What happens |
|------|--------------|
| **1 — Requirements & Template** | Upload the two `.xlsx` files. Click **Load bundled samples** to use the files already on this machine. The parser handles both checklist layouts (ref in a column, or `"1.1 …"` inline with an `Annexure` marker + *Responsible Department* column) and, when the workbook holds several requirement sheets, auto-picks the richest one — switch via the **Worksheet** dropdown. |
| **2 — Customer Files & Matcher** | Drag in files or whole section folders (structure preserved). Run the matcher. |
| **3 — Review & Export** | Interactive parsed-vs-missing table (override any row), one-click **workbook** and **email** download. |

Sessions persist in `backend/storage/<id>/`; the browser remembers the last
session id in `localStorage`.

## Learning from auditor corrections

Every override on the review screen — changing a status, attaching a document,
detaching one — is appended to `backend/storage/learned/feedback.jsonl` (global,
survives restarts). Before each future matching run the matcher consults it:

* a file that previously **confirmed** a requirement is boosted — strongly if the
  exact filename recurs (common across audit periods), softly by shared filename
  tokens (`VAT 201 Return…`, `Trial Balance…`);
* a file previously **detached** from a requirement is penalised / dropped;
* a status repeatedly set by hand (especially `Not applicable`) is applied as a
  hint when no strong document match exists.

Rows influenced this way are flagged with a brain icon and a note. `MatchStats.learned_applied`
counts them. Manage via `GET /api/learning` (stats) and `DELETE /api/learning`
(reset) — the review screen shows the count and a Reset link.

## Outputs

**1. Populated working-paper workbook** (`RERA_Interim_Audit_Workpapers.xlsx`)

* Sheets **`17. PBC Checklist Status`** / **`18. Requirements Tracker`** — status,
  remarks, follow-up flags, received dates; requirement text filled into the
  blank column; summary counts become `COUNTIF` formulas; status cells recoloured
  green / amber / red to match the word.
* **Entity, dates & place** read from the customer files (developer trade licence,
  KYC, appointment letters) and substituted across *every* sheet — JOP name,
  developer name + licence no. + expiry, registered address, management company,
  reporting period (`As at` date headers included). Editable on the review screen;
  each auto-filled value shows the file it came from.
* **`2 _IS`** / **`3 BS`** — line items are written as **live cross-sheet
  references** to the supporting annexures where those were populated
  (`='10. bank balances'!K25`, `='13 accruals'!O39`, `='4_other income'!I24`,
  `='12. supplier balance'!…`); everything else is a value from the trial
  balance. Sub-totals / totals / the balance check are `SUM` / difference
  formulas — existing template formulas are never overwritten.
* **`1_project details`**, **`4_other income`**, **`10. bank balances`**,
  **`12. supplier balance`**, **`13 accruals`**, **`16. Notes Summary`** populated
  where the source data can be read.
* **Audit Report — Procedures &amp; Findings table** — the RERA agreed-upon-procedures
  matrix (13 blocks, ~55 procedures from the scope document) is written into the
  Audit Report sheet as a bordered *Procedures | Findings* table. Findings default
  to "No exceptions noted." and are specialised from the extracted figures
  (bank closings, supplier / accrual totals, ECL provision, trade-licence
  verification, "Not applicable" where the JOP has no such item). With an LLM key
  the findings are re-drafted from the actual customer files. Defined in
  `services/procedures.py`.
* **LLM workbook pass** (when a key is set) — a 4-step pipeline in
  `services/workbook_llm.py`:
  1. **classify** each customer spreadsheet (trial balance, bank, invoice
     schedule, budget, collection report, GL extract);
  2. **extract** — one small-model call per financial file turns the raw rows
     (a Mollak trial balance is ~450) into a structured JSON of accounting facts
     (income / expenditure / assets / liabilities lines, fund balances, bank
     closings, unit-receivable total, supplier balances, budget lines);
  3. **consolidate** into one FactBook;
  4. **map** — the FactBook + each sheet's exact layout go to the main model,
     which returns the cell writes to populate *every* data cell (2 sheets per
     call to stay under free-tier limits). Totals / sub-totals / differences /
     cross-sheet references are written as Excel formulas; a cell is left blank
     only when the FactBook has nothing for it.
  Guardrails: never overwrites an existing formula or a text label; appended
  cells inherit the style of the rows above; every write is logged with its
  provider. Rate-limit / transient errors are retried with the server-suggested
  delay. ~9 model calls per workbook on Groq; extraction is cached per file so
  regenerating is fast.

**2. Filled requirements checklist** (`Requirements_Checklist_Filled.xlsx`)

A completed copy of the *original* requirements workbook — STATUS
(Provided / Provided (partial) / Pending / N/A, colour-coded) and REMARKS (mapped
file names or what is outstanding) filled per row, and the *Audit Period* banner
refreshed to the period detected from the customer files. Styles, column widths
and the `=TODAY()` date formula are preserved.

Notes: anything the pipeline can't source confidently is listed in the generation
report's *"notes for manual review"* — nothing is invented. `openpyxl` does not
preserve embedded charts/images; formatting, styles, number formats and formulas
are preserved. The `3 BS` balance-check row stays non-zero until the auditor
completes figures the client hasn't provided (opening funds, service-charge
income, receivables) — expected for an interim file.

## Deploy to Railway

The repo ships a **single-service** setup: a multi-stage `Dockerfile` builds the
React app and the FastAPI backend serves it alongside the API (same origin, no
CORS to configure).

1. **Push this repo to GitHub.**
2. On [railway.app](https://railway.app): **New Project → Deploy from GitHub repo**,
   pick this repo. Railway detects `Dockerfile` / `railway.json` automatically.
3. **Variables** (service → Variables):
   | Variable | Value |
   |---|---|
   | `GROQ_API_KEY` | your free key from console.groq.com (enables the LLM passes) |
   | `STORAGE_DIR` | `/data` |
   `RAILWAY_PUBLIC_DOMAIN` and `PORT` are injected automatically.
4. **Add a Volume** (service → Settings → Volumes) mounted at **`/data`** so the
   learning store (`/data/learned/feedback.jsonl`) and generated files survive
   redeploys. Without a volume the app still runs, but that state is ephemeral.
5. **Deploy.** Railway builds the image (~4 min), runs
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`, and health-checks
   `/api/health`. Open the generated URL — the wizard is at `/`, API docs at `/docs`.

Notes
* **Single worker only** — the session store is in-process; multiple workers/replicas
  would split sessions. `railway.json` pins `numReplicas: 1`.
* Recommended plan size: **≥ 1 GB RAM** (PDF + pandas parsing of large uploads).
* The two demo workbooks are baked into the image so **"Load bundled samples"**
  works; the sample *documents* folder is not shipped — upload your own.
* Local `docker build -t rera-audit . && docker run -p 8000:8000 -e PORT=8000 rera-audit`
  reproduces the deployment.

### Two-service alternative

Prefer separate services? Deploy `backend/` (root dir `backend`, start
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`) and `frontend/` (static site,
build `npm ci && npm run build`, publish `dist`) as two Railway services, then set
`ALLOWED_ORIGINS=https://<frontend-domain>` on the backend and
`VITE_API_TARGET`/a rewrite so the frontend's `/api` calls reach the backend.

## Environment variables (backend)

See `backend/.env.example`. Highlights: `ANTHROPIC_API_KEY`, `LLM_MODEL`
(default `claude-opus-5`), `ALLOWED_ORIGINS`, `ALLOW_LOCAL_SAMPLES`,
`MAX_UPLOAD_MB`.

## Legacy `.xls`

Reading `.xls` requires `xlrd >= 2.0.1` (pinned in `requirements.txt`). If a
globally-installed `xlrd 1.x` shadows it, `pip install -U xlrd` inside the venv.
