import { describe, expect, it } from "vitest";
import { clock, pct } from "./format";

describe("clock", () => {
  it("maps simulation minutes onto the clinic clock", () => {
    expect(clock(8, 0)).toBe("08:00");
    expect(clock(8, 65)).toBe("09:05");
    expect(clock(8, 480)).toBe("16:00");
  });
});

describe("pct", () => {
  it("renders a share as a percent", () => {
    expect(pct(0.964)).toBe("96%");
  });
});
