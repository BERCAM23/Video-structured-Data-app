import { useRef, useState } from "react";

export default function UploadZone({ onFile }: { onFile: (f: File) => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handle = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await onFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
      setBusy(false);
    }
  };

  return (
    <main className="upload">
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handle(e.dataTransfer.files[0]); }}
        onClick={() => inputRef.current?.click()}
      >
        <h1>Sube una transmision</h1>
        <p>MP4, MOV o MKV. Maximo 3 horas.</p>
        <p className="hint">{busy ? "Subiendo..." : "Arrastra el archivo o haz clic"}</p>
        {error && <p className="error">{error}</p>}
        <input
          ref={inputRef} type="file" accept=".mp4,.mov,.mkv" hidden
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </div>
    </main>
  );
}
