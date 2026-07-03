import { describe, expect, it } from "vitest";
import { fmtTs, splitCitations } from "./time";

describe("fmtTs", () => {
  it("formats minutes and hours", () => {
    expect(fmtTs(0)).toBe("00:00");
    expect(fmtTs(65)).toBe("01:05");
    expect(fmtTs(3725)).toBe("1:02:05");
  });
});

describe("splitCitations", () => {
  it("splits text and citations with seconds", () => {
    const parts = splitCitations("Gol al [01:05] y festejo al [1:02:05].");
    expect(parts).toEqual([
      { kind: "text", value: "Gol al " },
      { kind: "cite", value: "[01:05]", seconds: 65 },
      { kind: "text", value: " y festejo al " },
      { kind: "cite", value: "[1:02:05]", seconds: 3725 },
      { kind: "text", value: "." },
    ]);
  });

  it("returns plain text when no citations", () => {
    expect(splitCitations("hola")).toEqual([{ kind: "text", value: "hola" }]);
  });
});
