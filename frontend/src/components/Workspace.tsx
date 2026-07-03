import { useRef, useState } from "react";
import { streamUrl, type Records } from "../lib/api";
import DataScroller from "./DataScroller";

export default function Workspace({ id, records }: { id: string; records: Records }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);

  const seek = (seconds: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = seconds;
    v.play().catch(() => {});
  };

  return (
    <main className="workspace">
      <section className="stage">
        <video
          ref={videoRef}
          src={streamUrl(id)}
          controls
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        />
        <div className="videometa">
          <h2>{records.video.title}</h2>
          <p className="muted">
            {records.video.sport} {records.video.teams ? `| ${records.video.teams}` : ""}
          </p>
          <p>{records.video.summary}</p>
        </div>
      </section>
      <DataScroller records={records} currentTime={currentTime} onSeek={seek} />
      <div className="chatslot" data-seek-target id={`chat-${id}`} />
    </main>
  );
}
