import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const pages = [
  { id: "tournament", title: "Iterated Prisoner’s Dilemma tournament" },
  { id: "moran", title: "Moran evolutionary process" },
  { id: "trust", title: "Investment / Trust Game" },
  { id: "sweeps", title: "Parameter sweeps" },
  { id: "guide", title: "Universal Trust Model" },
];

for (const width of [1440, 390]) {
  for (const tool of pages) {
    test(`${tool.id}: scientific scope, prose, and layout at ${width}px`, async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(`/?view=${tool.id}`);
      await expect(
        page.getByRole("heading", { name: tool.title, exact: true }),
      ).toBeVisible();
      await expect(page.locator("footer small")).toContainText("Build", {
        timeout: 60_000,
      });
      if (tool.id === "guide") {
        await expect(
          page
            .getByRole("article")
            .getByRole("heading", { name: "References", exact: true }),
        ).toBeVisible();
      }
      for (const details of await page.locator("details").all()) {
        if (
          !(await details.evaluate(
            (element) => (element as HTMLDetailsElement).open,
          ))
        ) {
          await details.locator(":scope > summary").click();
        }
      }
      await expect(page.locator("footer")).toContainText(
        "Software checks and reproducible simulations do not establish human behavioral validity.",
      );
      if (tool.id === "tournament") {
        await expect(page.locator(".hero > .eyebrow")).toHaveText(
          "PRIMARY EXPERIMENT / IPD",
        );
        await expect(page.locator(".study-context")).toContainText(
          "Rankings depend on the opponent field",
        );
        await expect(
          page.getByRole("group", {
            name: "UTM parameter presets",
            exact: true,
          }),
        ).toContainText(
          "not measured human personality types or validated behavioral classifications",
        );
      } else if (tool.id !== "guide") {
        await expect(page.locator(".hero > .eyebrow")).toHaveText(
          "EXPLORATORY EXPERIMENT / UTM",
        );
      }
      if (["tournament", "moran", "trust"].includes(tool.id)) {
        await expect(page.getByRole("slider")).toHaveCount(5);
        await expect(
          page.getByText(
            "Trust is a model state, not a calibrated probability or a measured human belief.",
          ),
        ).toBeVisible();
        const fields = [
          {
            name: "Initial trust",
            step: 0.01,
            help: "Initial trust value before the first interaction.",
          },
          {
            name: "Positive learning rate",
            step: 0.001,
            help: "Learning rate when the signed reward exceeds current trust.",
          },
          {
            name: "Negative learning rate",
            step: 0.001,
            help: "Learning rate when the signed reward is at or below current trust.",
          },
          {
            name: "Cumulative update ramp",
            step: 0.01,
            help: "Counts rewards below current trust, including the current event. The cumulative multiplier scales current and later updates in both directions. It is not a count of consecutive defections.",
          },
          {
            name:
              tool.id === "trust"
                ? "Investment threshold"
                : "Cooperation threshold",
            step: 0.01,
            help: "Trust threshold used by the selected decision rule.",
          },
        ];
        const ids: string[] = [];
        for (const field of fields) {
          const slider = page.getByRole("slider", {
            name: field.name,
            exact: true,
          });
          await expect(slider).toHaveAccessibleName(field.name);
          await expect(slider).toHaveAccessibleDescription(field.help);
          const id = await slider.getAttribute("id");
          expect(id).toBeTruthy();
          ids.push(id!);
          expect(
            await slider.evaluate((input) => {
              const range = input as HTMLInputElement;
              const label = range.labels?.[0];
              const output = range
                .closest(".slider-field")
                ?.querySelector("output");
              return (
                label?.htmlFor === range.id &&
                label.control === range &&
                output?.getAttribute("for") === range.id
              );
            }),
          ).toBe(true);
          const before = Number(await slider.inputValue());
          await slider.focus();
          await slider.press("ArrowRight");
          expect(Number(await slider.inputValue())).toBeCloseTo(
            before + field.step,
            12,
          );
          await expect(slider).toHaveAttribute("id", id!);
          await slider.press("ArrowLeft");
          expect(Number(await slider.inputValue())).toBeCloseTo(before, 12);
          await expect(
            page.getByRole("status", {
              name: `${field.name} current value`,
              exact: true,
            }),
          ).toHaveText(before.toFixed(field.step < 0.01 ? 3 : 2));
        }
        expect(new Set(ids).size).toBe(5);
        expect(
          await page
            .getByRole("slider", { name: "Betrayal ramp", exact: true })
            .count(),
        ).toBe(0);
      }
      if (tool.id === "moran") {
        await expect(page.locator(".study-context")).toContainText(
          "neutral drift, random changes without a payoff advantage",
        );
        await expect(page.locator(".study-context")).toContainText(
          "unfinished trajectory",
        );
        await expect(page.locator(".study-context")).toContainText(
          "One trajectory does not estimate fixation probability",
        );
      }
      if (tool.id === "trust") {
        await expect(page.locator(".study-context")).toContainText(
          "reward +1 for nonnegative payoff, including zero when no investment is made",
        );
        await expect(page.locator(".environment-intro")).toContainText(
          "recovery without fresh partner evidence",
        );
        await expect(page.locator(".study-context")).toContainText(
          "rather than interpreting zero-payoff rounds as cooperation",
        );
      }
      if (tool.id === "sweeps") {
        await expect(page.locator(".study-context")).toContainText(
          "does not establish an optimum",
        );
        await expect(page.locator(".reading")).toContainText(
          "32 combinations, 100 rounds, 5 repetitions, and 10 players",
        );
        await expect(page.locator(".reading")).toContainText(
          "60-second execution budget is checked between simulations",
        );
        await expect(page.locator(".reading pre").first()).toHaveText(
          "ENABLE_SWEEP_UI=true poetry run streamlit run dash/pages/01_IPD_Mini_Sweep.py",
        );
        await expect(page.locator(".reading")).toContainText(
          "separate from the Prisoner’s Dilemma game payoffs",
        );
      }
      if (tool.id === "guide") {
        const guide = page.getByRole("article");
        await expect(guide).toContainText(
          "not automatically a calibrated probability",
        );
        await expect(guide).toContainText(
          "does not implement this complete multi-cue model",
        );
        await expect(guide).toContainText(
          "No experiment here demonstrates that UTM resolves documented limitations",
        );
        await expect(guide).toContainText(
          "do not establish trust-risk separation",
        );
        await expect(guide).toContainText("neutral drift");
        await expect(guide.locator(".katex-display")).toHaveCount(5);
        await expect(guide.getByRole("table")).toHaveCount(4);
        await expect(guide.locator(".katex-error")).toHaveCount(0);
      }
      const prose = await page.locator("main").evaluate((element) => {
        const copy = element.cloneNode(true) as HTMLElement;
        // Raw data, third-party opponent names, and math are not authored prose.
        copy
          .querySelectorAll(
            "pre,textarea,input,svg,output,.opponent-list,.katex,math",
          )
          .forEach((node) => node.remove());
        return copy.textContent ?? "";
      });
      expect(prose).not.toContain("\u2014");
      await page.evaluate(() => document.fonts.ready);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      expect(errors).toEqual([]);
    });
  }
}

test("preset selection shows variants, illustrative descriptions, and unchanged identities", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Run simulation →" }),
  ).toBeEnabled({ timeout: 60_000 });
  const presets = page.getByRole("group", {
    name: "UTM parameter presets",
    exact: true,
  });
  await presets.locator(":scope > summary").click();
  await expect(presets).toContainText(
    "Each preset can use a different strategy variant and parameters from the focal agent",
  );
  const expected = [
    ["The Diplomat", "TFT"],
    ["The Maverick", "WSLS"],
    ["The Guardian", "TFT"],
    ["The Opportunist", "WSLS"],
    ["The Visionary", "TFT"],
    ["The Sentinel", "TFT→WSLS"],
    ["The Altruist", "TFT"],
    ["The Trickster", "WSLS"],
  ];
  await expect(presets.getByRole("checkbox")).toHaveCount(8);
  for (const [name, variant] of expected) {
    const option = presets.locator("label").filter({
      has: page.getByRole("checkbox", { name: new RegExp(`^${name}`) }),
    });
    await expect(option).toContainText(`Variant: ${variant}`);
    await expect(option).not.toContainText("\u2014");
  }
  await presets.getByRole("checkbox", { name: /^The Diplomat/ }).check();
  await presets.getByRole("checkbox", { name: /^The Sentinel/ }).check();
  const request = page.waitForRequest("**/api/run/tournament");
  await page.route("**/api/run/tournament", (route) =>
    route.fulfill({
      contentType: "application/x-ndjson",
      body: '{"type":"error","message":"Selection captured without simulation."}\n',
    }),
  );
  await page.getByRole("button", { name: "Run simulation →" }).click();
  expect((await request).postDataJSON().presets).toEqual([
    "The Diplomat",
    "The Sentinel",
  ]);
});

test("omitted preset settings display the focal variant and parameters", async ({
  page,
}) => {
  await page.route("**/api/catalogue", async (route) => {
    const response = await route.fetch();
    const catalogue = await response.json();
    await route.fulfill({
      json: {
        ...catalogue,
        presets: {
          "Inherited settings": {
            creator: "Test fixture",
            description: "Omitted settings inherit the focal configuration.",
          },
        },
      },
    });
  });
  await page.goto("/");
  await expect(page.locator("footer small")).toContainText("Build", {
    timeout: 60_000,
  });
  await page.getByLabel("Strategy variant").selectOption("WSLS");
  const presets = page.getByRole("group", {
    name: "UTM parameter presets",
    exact: true,
  });
  await presets.locator(":scope > summary").click();
  await expect(presets).toContainText(
    "Variant: WSLS · θ 0.6 · α⁺ 0.02 · α⁻ 0.675 · δ 0.45 · τ 0.5",
  );
  await page
    .getByRole("slider", { name: "Initial trust", exact: true })
    .focus();
  await page
    .getByRole("slider", { name: "Initial trust", exact: true })
    .press("ArrowRight");
  await expect(presets).toContainText("Variant: WSLS · θ 0.61");
});

test("suggestion dialog uses parameter terminology without submitting a suggestion", async ({
  page,
}) => {
  let submissions = 0;
  page.on("request", (request) => {
    if (
      request.url().endsWith("/api/suggestions") &&
      request.method() === "POST"
    )
      submissions++;
  });
  await page.route("**/api/catalogue", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: { ...(await response.json()), submissions_enabled: true },
    });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Suggest these UTM parameters as a preset ↗" })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Suggest a parameter preset",
    exact: true,
  });
  await expect(dialog).toContainText(
    "not measured personality types or validated behavioral classifications",
  );
  await expect(dialog).toContainText(
    "Distinguish untested expectations from observations",
  );
  await expect(
    dialog.getByLabel("Parameter rationale and untested expectations"),
  ).toBeVisible();
  expect(await dialog.innerText()).not.toContain("\u2014");
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  expect(submissions).toBe(0);
});

test("bounded local IPD run retains resolved preset identities and the reviewed payoff matrix", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Run simulation →" }),
  ).toBeEnabled({ timeout: 60_000 });
  await page.getByLabel("Strategy variant").selectOption("Trust-only IPD");
  const opponents = page.getByRole("group", { name: "Opponent options" });
  while (await opponents.getByRole("checkbox", { checked: true }).count()) {
    await opponents.getByRole("checkbox", { checked: true }).first().uncheck();
  }
  const search = page.getByRole("searchbox", {
    name: "Filter opponents by name",
  });
  for (const name of ["Cooperator", "Defector"]) {
    await search.fill(name);
    await opponents.getByRole("checkbox", { name, exact: true }).check();
  }
  const presets = page.getByRole("group", {
    name: "UTM parameter presets",
    exact: true,
  });
  await presets.locator(":scope > summary").click();
  for (const name of ["The Diplomat", "The Sentinel"])
    await presets
      .getByRole("checkbox", { name: new RegExp(`^${name}`) })
      .check();
  await page.getByLabel("Rounds per match", { exact: true }).fill("20");
  await page.getByLabel("Repetitions", { exact: true }).fill("2");
  const requested = page.waitForRequest("**/api/run/tournament");
  await page.getByRole("button", { name: "Run simulation →" }).click();
  const config = (await requested).postDataJSON();
  expect(config).toEqual({
    theta: 0.6,
    alpha_pos: 0.02,
    alpha_neg: 0.675,
    delta: 0.45,
    threshold: 0.5,
    variant: "Trust-only IPD",
    seed: 42,
    rounds: 20,
    repetitions: 2,
    opponents: ["Cooperator", "Defector"],
    presets: ["The Diplomat", "The Sentinel"],
    extra_opponent: "None",
    noise_wrap: false,
    noise_pct: 0,
  });
  await expect(page.getByText("Run complete")).toBeVisible({ timeout: 60_000 });
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "↓ Results + settings" }).click();
  const download = await downloading;
  const result = JSON.parse(await readFile((await download.path())!, "utf8"));
  const identities = result.metadata.resolved_players.map(
    (entry: { label: string }) => entry.label.split(":", 1)[0],
  );
  const order = [
    "Trust-only IPD",
    "Cooperator",
    "Defector",
    "UTM-The Diplomat",
    "UTM-The Sentinel",
  ];
  expect(identities).toEqual(order);
  const expected = [
    [3, 3, 0.95, 3, 0.95],
    [3, 3, 0, 3, 0],
    [1.2, 5, 1, 1.2, 1],
    [3, 3, 0.95, 3, 0.95],
    [1.2, 5, 1, 1.2, 1],
  ];
  for (const [row, name] of order.entries()) {
    const actual = order.map(
      (opponent) =>
        result.payoff_matrix[identities.indexOf(name)][
          identities.indexOf(opponent)
        ],
    );
    expect(actual).toEqual(expected[row]);
  }
  expect(result.config).toEqual(config);
  for (const row of result.leaderboard) expect(row["#C"] + row["#D"]).toBe(160);
  const sentinel = result.leaderboard.find(
    (row: { "Player index": number }) =>
      row["Player index"] === identities.indexOf("UTM-The Sentinel"),
  );
  expect(sentinel["#C"]).toBe(0);
  expect(sentinel["#D"]).toBe(160);
  expect(sentinel["C-rate"]).toBe(0);
  await expect(
    page.getByRole("region", { name: "Simulation results" }),
  ).toContainText("UTM-The Sentinel");
});
