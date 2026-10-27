import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const players = [
  "UTM-TitForTat: 0.6, 0.02, 0.675, 0.45, 0.5",
  "Tit For Tat",
  "Defector",
  "Random: 0.5",
];
const scores = [
  [4, 1, 3, 2],
  [2.49, 2.5, 2.51, 2.5],
  [3, 3, 3, 3],
  [0, 5, 0, 5],
];

for (const width of [1440, 390]) {
  test.describe(`score distribution at ${width}px`, () => {
    test.use({ viewport: { width, height: 1000 }, hasTouch: width === 390 });
    test("shows the payoff scale, inspectable statistics, and unmodified downloads", async ({
      page,
    }) => {
      await page.route("**/api/run/tournament", (route) =>
        route.fulfill({
          contentType: "application/x-ndjson",
          body:
            JSON.stringify({
              type: "result",
              result: {
                kind: "tournament",
                config: route.request().postDataJSON(),
                players,
                scores,
                leaderboard: players.map((Player) => ({ Player, Mean: 2.5 })),
              },
            }) + "\n",
        }),
      );
      await page.goto("/");
      await page.getByRole("button", { name: "Run simulation →" }).click();
      const chart = page.getByRole("region", {
        name: "Score distribution",
        exact: true,
      });
      await expect(chart).toBeVisible();
      await expect(chart.locator(".score-axis")).toHaveAttribute(
        "aria-label",
        "Shared payoff scale: 0 to 5",
      );
      await expect(chart.locator(".score-ticks span")).toHaveText([
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
      ]);
      await expect(chart).toContainText("Self-play is excluded");
      await expect(chart).toContainText("Box: middle 50%");
      await expect(chart).toContainText(
        "not across opponents or a confidence interval",
      );
      const first = chart.getByRole("button", {
        name: `1. ${players[0]}: score distribution`,
        exact: true,
      });
      await expect(first.locator(".score-name")).toHaveText(`1. ${players[0]}`);
      expect(
        await first.evaluate((element) => getComputedStyle(element).fontSize),
      ).toBe("12px");
      await expect(first.locator(".score-median strong")).toHaveText("2.500");
      await first.hover();
      const tooltip = chart.getByRole("tooltip");
      await expect(tooltip.locator("dd")).toHaveText([
        "4",
        "1",
        "1.75",
        "2.5",
        "3.25",
        "4",
      ]);
      await tooltip.hover();
      await expect(tooltip).toBeVisible();
      await page
        .getByRole("heading", { name: "Score distribution", exact: true })
        .hover();
      await expect(tooltip).toHaveCount(0);
      await first.focus();
      await expect(first).toHaveAccessibleDescription(/First quartile.*1.75/);
      await first.press("Escape");
      await expect(tooltip).toHaveCount(0);
      await first.press("Enter");
      await expect(first).toHaveAttribute("aria-expanded", "true");
      const expanded = chart.getByRole("region", {
        name: `1. ${players[0]}: repetition statistics`,
        exact: true,
      });
      await expect(expanded).toBeVisible();
      await first.press("Enter");
      await expect(expanded).toHaveCount(0);
      const equal = chart.getByRole("button", {
        name: "3. Defector: score distribution",
        exact: true,
      });
      if (width === 390) await equal.tap();
      else await equal.click();
      await expect(equal).toHaveAttribute("aria-expanded", "true");
      await expect(chart).toContainText("All repetition scores are equal");
      await expect(equal.locator("circle")).toHaveCount(1);
      const fit = chart.getByRole("checkbox", {
        name: "Fit scale to observed scores",
      });
      await fit.check();
      await expect(chart).toContainText("(observed range)");
      await fit.uncheck();
      await expect(chart.locator(".score-axis")).toHaveAttribute(
        "aria-label",
        "Shared payoff scale: 0 to 5",
      );
      await page.evaluate(() => document.fonts.ready);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      const downloading = page.waitForEvent("download");
      await page.getByRole("button", { name: "↓ Results + settings" }).click();
      const downloaded = JSON.parse(
        await readFile((await (await downloading).path())!, "utf8"),
      );
      expect(downloaded.scores).toEqual(scores);
      expect(downloaded.players).toEqual(players);
    });

    test("explains single repetitions and can enlarge a narrow observed range", async ({
      page,
    }) => {
      await page.route("**/api/run/tournament", (route) =>
        route.fulfill({
          contentType: "application/x-ndjson",
          body:
            JSON.stringify({
              type: "result",
              result: {
                kind: "tournament",
                config: route.request().postDataJSON(),
                players: ["Cooperator", "Tit For Tat"],
                scores: [[2.49], [2.51]],
                leaderboard: [
                  { Player: "Cooperator", Mean: 2.49 },
                  { Player: "Tit For Tat", Mean: 2.51 },
                ],
              },
            }) + "\n",
        }),
      );
      await page.goto("/");
      await page.getByRole("button", { name: "Run simulation →" }).click();
      const chart = page.getByRole("region", {
        name: "Score distribution",
        exact: true,
      });
      const row = chart.getByRole("button", {
        name: "1. Cooperator: score distribution",
        exact: true,
      });
      const marker = row.locator("circle");
      const before = Number(await marker.getAttribute("cx"));
      await chart
        .getByRole("checkbox", { name: "Fit scale to observed scores" })
        .check();
      expect(Number(await marker.getAttribute("cx"))).toBeLessThan(before);
      await row.click();
      await expect(chart).toContainText(
        "One repetition: spread cannot be assessed",
      );
      await expect(chart.locator(".score-values dd").first()).toHaveText("1");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
    });
  });
}
