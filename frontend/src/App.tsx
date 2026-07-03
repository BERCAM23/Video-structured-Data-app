import { useCallback, useEffect, useRef, useState } from "react";
import { getRecords, getStatus, uploadVideo, type Records } from "./lib/api";
import UploadZone from "./components/UploadZone";
import ProcessingView from "./components/ProcessingView";
import Workspace from "./components/Workspace";

type Phase =
  | { name: "upload" }
  | { name: "processing"; id: string; status: string; error: string | null }
  | { name: "workspace"; id: string; records: Records };

export default function App() {
  const [phase, setPhase] = useState<Phase>({ name: "upload" });
  const pollRef = useRef<number | null>(null);

  const startPolling = useCallback((id: string) => {
    const tick = async () => {
      try {
        const s = await getStatus(id);
        if (s.status === "ready") {
          if (pollRef.current) window.clearInterval(pollRef.current);
          const records = await getRecords(id);
          setPhase({ name: "workspace", id, records });
        } else {
          setPhase({ name: "processing", id, status: s.status, error: s.error });
          if (s.status === "failed" && pollRef.current) window.clearInterval(pollRef.current);
        }
      } catch {
        /* transient poll error: keep polling */
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2000);
  }, []);

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);

  const onFile = async (file: File) => {
    const { id } = await uploadVideo(file);
    setPhase({ name: "processing", id, status: "uploaded", error: null });
    startPolling(id);
  };

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">FOX <b>VIDEO INTELLIGENCE</b></span>
      </header>
      {phase.name === "upload" && <UploadZone onFile={onFile} />}
      {phase.name === "processing" && (
        <ProcessingView status={phase.status} error={phase.error} />
      )}
      {phase.name === "workspace" && <Workspace id={phase.id} records={phase.records} />}
    </div>
  );
}
