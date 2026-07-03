const STAGES = [
  { keys: ["uploaded", "extracting_audio"], label: "Preparando audio" },
  { keys: ["transcribing"], label: "Transcribiendo con hablantes" },
  { keys: ["analyzing_visuals"], label: "Analizando video cuadro a cuadro" },
  { keys: ["summarizing"], label: "Generando resumenes" },
];

export default function ProcessingView({ status, error }: { status: string; error: string | null }) {
  const activeIdx = STAGES.findIndex((s) => s.keys.includes(status));
  return (
    <main className="processing">
      <h1>Procesando la transmision</h1>
      <ol>
        {STAGES.map((s, i) => (
          <li
            key={s.label}
            className={
              status === "failed" ? "" : i < activeIdx ? "done" : i === activeIdx ? "active" : ""
            }
          >
            {s.label}
          </li>
        ))}
      </ol>
      {status === "failed" && <p className="error">Fallo el procesamiento: {error}</p>}
    </main>
  );
}
