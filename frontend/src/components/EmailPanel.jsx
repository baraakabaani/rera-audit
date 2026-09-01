import { useEffect, useState } from "react";
import { Copy, Check, Download, Mail, RefreshCw } from "lucide-react";
import { Card, CardHeader, CardTitle, CardBody } from "./ui/card";
import { Button } from "./ui/button";
import { api } from "../api";

export function EmailPanel({ session, refreshKey }) {
  const [email, setEmail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setEmail(await api.getEmail(session.id));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const copy = async () => {
    if (!email) return;
    await navigator.clipboard.writeText(`Subject: ${email.subject}\n\n${email.body_text}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-brand-600" /> Client follow-up email
        </CardTitle>
        <Button size="sm" variant="ghost" onClick={load} disabled={loading}>
          <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
        </Button>
      </CardHeader>
      <CardBody className="space-y-3">
        {error && <p className="text-sm text-rose-600">{error}</p>}
        {email && (
          <>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <span className="text-slate-400">Subject:&nbsp;</span>
              <span className="font-medium text-slate-700">{email.subject}</span>
            </div>
            <pre className="max-h-96 overflow-auto scroll-thin whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 text-xs leading-relaxed text-slate-700">
              {email.body_text}
            </pre>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={copy}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copied" : "Copy to clipboard"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                as="a"
                href={api.emailDownloadUrl(session.id, "eml")}
              >
                <Download className="h-4 w-4" /> .eml
              </Button>
              <Button
                size="sm"
                variant="outline"
                as="a"
                href={api.emailDownloadUrl(session.id, "txt")}
              >
                <Download className="h-4 w-4" /> .txt
              </Button>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
