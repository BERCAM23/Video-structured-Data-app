import { useRef, useState } from "react";
import type { VideoListItem } from "../lib/api";

type Props = {
  onFile: (f: File) => Promise<void>;
  videos: VideoListItem[];
  onOpen: (id: string) => void;
};

export default function UploadZone({ onFile, videos, onOpen }: Props) {
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
    <div className="upload-col">
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
      {videos.length > 0 && (
        <div className="recent">
          <h2>Videos procesados</h2>
          {videos.map((v) => (
            <button key={v.id} className="recent-item" onClick={() => onOpen(v.id)}>
              <span>{v.title}</span>
              <span className="muted">
                {v.status === "ready" ? "listo" : v.status === "failed" ? "fallo" : "procesando..."}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
