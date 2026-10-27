import { describe, expect, it } from "vitest";
import { scoreScale, summarizeScores } from "./score-distribution";

describe("repetition score summaries", () => {
  it("preserves interpolated quartiles and the original score order", () => {
    const scores = [4, 1, 3, 2];
    expect(summarizeScores(scores)).toEqual([1, 1.75, 2.5, 3.25, 4]);
    expect(scores).toEqual([4, 1, 3, 2]);
    expect(summarizeScores([0, 5])).toEqual([0, 1.25, 2.5, 3.75, 5]);
  });
  it("represents equal and single observations without inventing spread", () => {
    expect(summarizeScores([3, 3, 3])).toEqual([3, 3, 3, 3, 3]);
    expect(summarizeScores([1.25])).toEqual([1.25, 1.25, 1.25, 1.25, 1.25]);
    expect(summarizeScores([])).toBeNull();
    expect(summarizeScores([3, NaN])).toBeNull();
  });
});

describe("shared score axis", () => {
  it("starts at the full public payoff range even for narrow observations", () => {
    expect(scoreScale([2.49, 2.5, 2.51], false)).toEqual({
      start: 0,
      end: 5,
      ticks: [0, 1, 2, 3, 4, 5],
    });
  });
  it("fits all observations with padding and a nonzero span for equal scores", () => {
    for (const scores of [[2.49, 2.51], [3, 3], [0], [5], []]) {
      const scale = scoreScale(scores, true);
      expect(scale.start).toBeLessThan(scale.end);
      for (const score of scores) {
        expect(scale.start).toBeLessThan(score);
        expect(scale.end).toBeGreaterThan(score);
      }
      expect(scale.ticks[0]).toBe(scale.start);
      expect(scale.ticks.at(-1)).toBeCloseTo(scale.end, 12);
      expect(scale.ticks.length).toBeLessThanOrEqual(8);
    }
  });
});
