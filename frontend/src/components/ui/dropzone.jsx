import { useRef, useState } from "react";
import { UploadCloud, FolderOpen, FilePlus2 } from "lucide-react";
import { cn } from "../../lib/utils";

/**
 * Drag & drop + click zone. Dropping or picking a folder recursively collects
 * every file inside it (all sub-folders), preserving relative paths.
 * onFiles receives a flat File[] (each with webkitRelativePath set).
 */
export function Dropzone({ onFiles, multiple = true, folder = true, busy = false, className }) {
  const fileRef = useRef(null);
  const folderRef = useRef(null);
  const [drag, setDrag] = useState(false);

  const emit = (list) => {
    const files = Array.from(list || []);
    if (files.length) onFiles(files);
  };

  // recursively walk a dropped directory entry
  const walkEntry = async (entry, path, out) => {
    if (entry.isFile) {
      await new Promise((resolve) =>
        entry.file((file) => {
          try {
            Object.defineProperty(file, "webkitRelativePath", {
              value: path + file.name,
              configurable: true,
            });
          } catch {
            /* some browsers freeze the prop */
          }
          out.push(file);
          resolve();
        }, resolve)
      );
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      // readEntries returns at most 100 at a time — loop until empty
      let batch;
      do {
        batch = await new Promise((res) => reader.readEntries(res, () => res([])));
        for (const e of batch) await walkEntry(e, path + entry.name + "/", out);
      } while (batch.length);
    }
  };

  const onDrop = async (e) => {
    e.preventDefault();
    setDrag(false);
    const items = e.dataTransfer.items;
    if (items && items.length && items[0].webkitGetAsEntry) {
      const out = [];
      const entries = Array.from(items)
        .map((it) => it.webkitGetAsEntry?.())
        .filter(Boolean);
      for (const entry of entries) await walkEntry(entry, "", out);
      if (out.length) return emit(out);
    }
    emit(e.dataTransfer.files);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-9 text-center transition-colors",
        drag ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-50",
        className
      )}
    >
      <UploadCloud className={cn("mb-2 h-9 w-9", drag ? "text-brand-600" : "text-slate-400")} />
      <p className="text-sm font-medium text-slate-700">
        {busy ? "Uploading & extracting…" : "Drag a folder (or files) here"}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        Everything inside the folder and its sub-folders is picked up automatically
      </p>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        {folder && (
          <button
            type="button"
            disabled={busy}
            onClick={() => folderRef.current?.click()}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            <FolderOpen className="h-4 w-4" /> Select a folder
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <FilePlus2 className="h-4 w-4" /> Add individual files
        </button>
      </div>

      <input
        ref={fileRef}
        type="file"
        hidden
        multiple={multiple}
        onChange={(e) => {
          emit(e.target.files);
          e.target.value = "";
        }}
      />
      {folder && (
        <input
          ref={folderRef}
          type="file"
          hidden
          webkitdirectory=""
          directory=""
          mozdirectory=""
          multiple
          onChange={(e) => {
            emit(e.target.files);
            e.target.value = "";
          }}
        />
      )}
    </div>
  );
}
