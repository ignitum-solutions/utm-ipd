import { test, expect } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`Model guide: IPD scope, learning comparison, equations, and references at ${width}px`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await page.getByRole("button", { name: /The Model/ }).click();
    const guide = page.getByRole("article");
    await expect(
      guide.getByRole("heading", {
        name: "Rescorla-Wagner and delta learning",
      }),
    ).toBeVisible();
    await expect(guide.locator(":scope > p").first()).toContainText(
      "Iterated Prisoner's Dilemma (IPD)",
    );
    await expect(guide.locator(":scope > p").first()).toContainText(
      "additional exploratory",
    );
    await expect(guide.locator(":scope > p").nth(1)).toContainText(
      "do not establish prediction of human trust",
    );
    await expect(guide.locator(":scope > p").nth(1)).toContainText(
      "trust-risk separation",
    );
    await expect(page.locator(".hero")).toContainText("Rescorla-Wagner");

    const comparison = guide.getByRole("table").filter({
      has: page.getByRole("columnheader", {
        name: "Single-cue fixed-rate learner",
      }),
    });
    for (const quantity of [
      "Current value",
      "Target outcome",
      "Prediction error",
      "Update strength",
    ]) {
      await expect(
        comparison.getByRole("cell", { name: quantity, exact: true }),
      ).toBeVisible();
    }
    await expect(
      comparison.getByRole("columnheader", { name: "Implemented UTM" }),
    ).toBeVisible();
    await expect(
      guide.getByText(/does not implement this complete multi-cue model/),
    ).toBeVisible();

    await expect(guide.locator(".katex-error")).toHaveCount(0);
    const equations = await guide
      .locator('.katex-display annotation[encoding="application/x-tex"]')
      .allTextContents();
    expect(
      equations.some(
        (tex) => tex.includes("V_{t+1}") && tex.includes("\\lambda_t - V_t"),
      ),
    ).toBe(true);
    expect(
      equations.some(
        (tex) =>
          tex.includes("T_{t+1}") &&
          tex.includes("\\operatorname{clip}_{[0,1]}"),
      ),
    ).toBe(true);
    expect(
      equations.some(
        (tex) => tex.includes("k_t =") && tex.includes("n_{t+1}\\delta"),
      ),
    ).toBe(true);
    expect(
      equations.some(
        (tex) => tex.includes("n_{t+1} = n_t +") && tex.includes("R_t < T_t"),
      ),
    ).toBe(true);
    await expect(guide.locator("math").first()).toBeAttached();

    const headings = await guide
      .getByRole("heading", { level: 2 })
      .allTextContents();
    const core = headings.indexOf("IPD rewards and tournament results");
    const auxiliary = headings.indexOf("Additional exploratory experiments");
    expect(core).toBeGreaterThanOrEqual(0);
    expect(auxiliary).toBeGreaterThan(core);
    for (const name of [
      "Investment / Trust Game",
      "Moran process",
      "Local parameter sweeps",
    ]) {
      await expect(
        guide.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
    }
    await expect(
      guide.getByText(/recovery without fresh partner evidence/),
    ).toBeVisible();
    await expect(
      guide.getByText(/Severity zero is not a missing-observation/),
    ).toBeVisible();
    await expect(
      guide.getByText(
        /software and mechanism checks, rather than empirical validation/,
      ),
    ).toBeVisible();
    const references = guide.locator("ul").last();
    await expect(references).toContainText(
      "Rescorla, R. A., and Wagner, A. R. (1972)",
    );
    await expect(references).toContainText(
      "Wilson, R. C., and Collins, A. G. E. (2019)",
    );
    await expect(
      references.getByRole("link", { name: "Chapter PDF" }),
    ).toHaveAttribute(
      "href",
      "https://www.columbia.edu/~rk566/Session4/Theory%20of%20Pavlovian%20Conditioning.pdf",
    );
    await expect(
      references.getByRole("link", { name: "Article", exact: true }),
    ).toHaveAttribute("href", "https://doi.org/10.7554/eLife.49547");

    // Check visible guide prose, excluding mathematical content and other tools.
    const prose = await guide.evaluate((element) => {
      const copy = element.cloneNode(true) as HTMLElement;
      copy.querySelectorAll(".katex, math").forEach((node) => node.remove());
      return copy.textContent ?? "";
    });
    const modelProse = `${await page.locator(".hero").innerText()} ${prose}`;
    expect(modelProse).not.toContain("\u2014");
    expect(modelProse).not.toMatch(/Rescorla[–—]Wagner/);

    for (const table of await guide.getByRole("table").all()) {
      const lastHeader = table.getByRole("columnheader").last();
      await lastHeader.scrollIntoViewIfNeeded();
      const readable = await lastHeader.evaluate((cell) => {
        const scroller = cell.closest(".table-scroll")!;
        const outer = scroller.getBoundingClientRect();
        const inner = cell.getBoundingClientRect();
        return scroller.clientWidth > 0 && inner.right <= outer.right + 1;
      });
      expect(readable).toBe(true);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("runs a seeded Trust Game through the local Python service and downloads results", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /03 Trust Game/ }).click();
  await expect(
    page.getByRole("button", { name: "Run simulation →" }),
  ).toBeEnabled({ timeout: 60_000 });
  await page.getByLabel("Rounds", { exact: true }).fill("25");
  await page.getByRole("button", { name: "Run simulation →" }).click();
  await expect(
    page.getByRole("region", { name: "Simulation progress" }),
  ).toBeVisible();
  await expect(page.getByText("Run complete")).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByRole("img", { name: /Trust trajectory/ }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Simulation results" })
      .getByRole("heading", { name: "Interpretation" }),
  ).toHaveCount(0);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "↓ Results + settings" }).click();
  const saved = await download;
  expect(saved.suggestedFilename()).toBe("utm-trust-reproduce.json");
  const { readFile } = await import("node:fs/promises");
  const result = JSON.parse(await readFile((await saved.path())!, "utf8"));
  expect(result.metadata.engine_revision).toBe("1");
  expect(result.metadata.protocol.zero_payoff_reward).toBe(1);
  await page.getByText("Run provenance and protocol", { exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Simulation results" }),
  ).toContainText("source_file_sha256");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Investment / Trust Game" }),
  ).toBeVisible();
});

test("guards internal navigation and removes the unload guard after leaving", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Run simulation →" }),
  ).toBeEnabled({ timeout: 60_000 });
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/run/tournament", async (route) => {
    await pending;
    await route.abort().catch(() => {});
  });
  try {
    await page.getByRole("button", { name: "Run simulation →" }).click();
    await expect(page.getByRole("button", { name: "Running…" })).toBeDisabled();
    await page.getByRole("button", { name: /02 Moran Process/ }).click();
    await expect(
      page.getByRole("dialog", { name: "Leave this active run?" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Stay here" }).click();
    await expect(
      page.getByRole("heading", {
        name: "Iterated Prisoner’s Dilemma tournament",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Simulation progress" }),
    ).toBeVisible();
    await page.getByRole("button", { name: /02 Moran Process/ }).click();
    await page.getByRole("button", { name: "Leave this run" }).click();
    await expect(
      page.getByRole("heading", { name: "Moran evolutionary process" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Simulation progress" }),
    ).toHaveCount(0);
    const unloaded = page
      .waitForEvent("dialog", { timeout: 700 })
      .then(() => true)
      .catch(() => false);
    await page.reload();
    expect(await unloaded).toBe(false);
  } finally {
    release();
  }
});

test("browser refresh offers its native warning during an active run", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Run simulation →" }),
  ).toBeEnabled({ timeout: 60_000 });
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/run/tournament", async (route) => {
    await pending;
    await route.abort().catch(() => {});
  });
  try {
    await page.getByRole("button", { name: "Run simulation →" }).click();
    await expect(
      page.getByRole("region", { name: "Simulation progress" }),
    ).toBeVisible();
    const dialogEvent = page.waitForEvent("dialog");
    // A dismissed beforeunload leaves the original document loading; bound the
    // automation's navigation wait independently of the user's decision.
    const reload = page.reload({ timeout: 3000 }).catch(() => {});
    const dialog = await dialogEvent;
    expect(dialog.type()).toBe("beforeunload");
    await dialog.dismiss();
    await reload;
    await expect(
      page.getByRole("region", { name: "Simulation progress" }),
    ).toBeVisible();
  } finally {
    release();
  }
});

test("renders the researcher controls on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Iterated Prisoner’s Dilemma tournament",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /IPD Tournament/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

for (const experiment of [
  { kind: "tournament", title: "Iterated Prisoner’s Dilemma tournament" },
  { kind: "moran", title: "Moran evolutionary process" },
  { kind: "trust", title: "Investment / Trust Game" },
]) {
  test(`${experiment.kind}: prioritizes run output and preserves results when parameters reopen`, async ({
    page,
  }) => {
    await page.goto(`/?view=${experiment.kind}`);
    await expect(
      page.getByRole("heading", { name: experiment.title, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Run simulation →" }),
    ).toBeEnabled({ timeout: 60_000 });
    const params = page.locator("#run-parameters");
    await expect(params).toHaveAttribute("open", "");
    expect(
      await page
        .getByRole("region", { name: "Run status and results", exact: true })
        .evaluate(
          (runPanel, parameters) =>
            Boolean(
              runPanel.compareDocumentPosition(parameters as Node) &
              Node.DOCUMENT_POSITION_FOLLOWING,
            ),
          await params.elementHandle(),
        ),
    ).toBe(true);
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    let requested: Record<string, unknown> = {};
    await page.route(`**/api/run/${experiment.kind}`, async (route) => {
      requested = route.request().postDataJSON();
      await pending;
      const result =
        experiment.kind === "tournament"
          ? {
              kind: "tournament",
              config: requested,
              leaderboard: [{ Player: "UTM", Mean: 3 }],
              players: ["UTM"],
              scores: [[3]],
              payoff_matrix: [[3]],
              wins: [[0]],
            }
          : {
              kind: experiment.kind,
              config: requested,
              series: [0.2, 0.4],
              summary:
                experiment.kind === "moran"
                  ? { "Final UTM share": 0.4 }
                  : { "Final trust": 0.4 },
              ...(experiment.kind === "trust" ? { cumulative: [1, 2] } : {}),
            };
      await route.fulfill({
        contentType: "application/x-ndjson",
        body: JSON.stringify({ type: "result", result }) + "\n",
      });
    });
    try {
      await page.getByRole("button", { name: "Run simulation →" }).click();
      await expect(
        page.getByRole("region", { name: "Simulation progress" }),
      ).toBeVisible();
      await expect(params).not.toHaveAttribute("open", "");
      await page.getByRole("button", { name: "View parameters ↓" }).click();
      await expect(params).toHaveAttribute("open", "");
      await expect(
        page.getByLabel("Random seed", { exact: true }),
      ).toBeDisabled();
      await params.locator(":scope > summary").click();
      release();
      await expect(page.getByText("Run complete")).toBeVisible();
      await expect(params).not.toHaveAttribute("open", "");
      await page.getByRole("button", { name: "Hide results" }).click();
      await expect(
        page.getByRole("region", { name: "Simulation results" }),
      ).toBeHidden();
      await page.getByRole("button", { name: "Show results" }).click();
      await expect(
        page.getByRole("region", { name: "Simulation results" }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Edit parameters ↓" }).click();
      await expect(params).toHaveAttribute("open", "");
      await expect(
        page.getByLabel("Random seed", { exact: true }),
      ).toBeEnabled();
      await page.getByLabel("Random seed", { exact: true }).fill("7");
      await page
        .getByText("Exact settings for this run", { exact: true })
        .click();
      await expect(
        page.getByRole("region", { name: "Simulation results" }).locator("pre"),
      ).toContainText('"seed": 42');
      expect(requested.seed).toBe(42);
    } finally {
      release();
    }
  });
}
