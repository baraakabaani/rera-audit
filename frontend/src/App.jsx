import { useEffect, useState } from "react";
import { ShieldCheck, Loader2 } from "lucide-react";
import { StepIndicator } from "./components/StepIndicator";
import { Step1Setup } from "./components/Step1Setup";
import { Step2Documents } from "./components/Step2Documents";
import { Step3Review } from "./components/Step3Review";
import { api } from "./api";

const SID_KEY = "rera.session.id";

export default function App() {
  const [booting, setBooting] = useState(true);
  const [session, setSession] = useState(null);
  const [health, setHealth] = useState({ llm_available: false });

  const [step, setStep] = useState(1);
  const [requirements, setRequirements] = useState(null);
  const [template, setTemplate] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [match, setMatch] = useState(null);
  const [learning, setLearning] = useState(null);

  const refreshLearning = async () => {
    try {
      setLearning(await api.getLearning());
    } catch {
      /* ignore */
    }
  };

  // -- boot: reuse or create a session, hydrate any prior state --------------
  useEffect(() => {
    (async () => {
      try {
        setHealth(await api.health());
      } catch {
        /* backend not up yet */
      }
      refreshLearning();
      let sess = null;
      const saved = localStorage.getItem(SID_KEY);
      if (saved) {
        try {
          sess = await api.getSession(saved);
        } catch {
          sess = null;
        }
      }
      if (!sess) {
        sess = await api.createSession();
        localStorage.setItem(SID_KEY, sess.id);
      }
      setSession(sess);

      if (sess.has_requirements) {
        try {
          setRequirements(await api.getRequirements(sess.id));
        } catch {}
      }
      if (sess.has_template) {
        try {
          setTemplate(await api.getTemplate(sess.id));
        } catch {}
      }
      if (sess.document_count) {
        try {
          setDocuments(await api.listDocuments(sess.id));
        } catch {}
      }
      if (sess.has_match) {
        try {
          setMatch(await api.getMatch(sess.id));
          setStep(3);
        } catch {}
      } else if (sess.has_template && sess.has_requirements) {
        setStep(2);
      }
      setBooting(false);
    })();
  }, []);

  const resetSession = async () => {
    if (session) await api.getSession(session.id).catch(() => {});
    const sess = await api.createSession();
    localStorage.setItem(SID_KEY, sess.id);
    setSession(sess);
    setRequirements(null);
    setTemplate(null);
    setDocuments([]);
    setMatch(null);
    setStep(1);
  };

  const maxStep = match ? 3 : requirements && template ? 2 : 1;

  if (booting) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Connecting to audit engine…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-800">RERA Audit Automation</h1>
            <p className="text-xs text-slate-400">
              Document ingestion · missing-item detection · workbook generation
            </p>
          </div>
          <button
            onClick={resetSession}
            className="ml-auto text-xs font-medium text-slate-400 hover:text-slate-600"
          >
            New session
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-6 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <StepIndicator step={step} maxStep={maxStep} onJump={setStep} />
        </div>

        {step === 1 && (
          <Step1Setup
            session={session}
            requirements={requirements}
            template={template}
            setRequirements={setRequirements}
            setTemplate={setTemplate}
            onNext={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <Step2Documents
            session={session}
            documents={documents}
            setDocuments={setDocuments}
            setMatch={setMatch}
            llmAvailable={health.llm_available}
            llmProvider={health.llm_provider}
            learning={learning}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}
        {step === 3 && match && (
          <Step3Review
            session={session}
            requirements={requirements}
            match={match}
            setMatch={setMatch}
            learning={learning}
            refreshLearning={refreshLearning}
            onBack={() => setStep(2)}
          />
        )}
      </div>

      <footer className="mx-auto max-w-6xl px-4 pb-8 pt-2 text-center text-xs text-slate-300">
        Generated working papers require auditor review before issuance.
      </footer>
    </div>
  );
}
