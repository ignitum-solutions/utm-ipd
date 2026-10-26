import { readFile } from 'node:fs/promises';
import { test, expect } from '@playwright/test';

test('filters names without losing selections or submitting the form on Enter', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Run simulation →' })).toBeEnabled({ timeout: 60_000 });
  const search = page.getByRole('searchbox', { name: 'Filter opponents by name' });
  const options = page.getByRole('group', { name: 'Opponent options' });
  await search.fill('tIT fOR');
  await expect(options.getByRole('checkbox', { name: 'Tit For Tat', exact: true })).toBeChecked();
  await options.getByRole('checkbox', { name: 'Tit For Tat', exact: true }).uncheck();
  await expect(page.locator('.opponent-picker .field-label')).toContainText('8 selected');
  await search.fill('no-such-strategy');
  await expect(options.getByRole('checkbox')).toHaveCount(0);
  await expect(options).toContainText('No opponents match');
  await page.getByRole('button', { name: 'Clear filter' }).click();
  await expect(search).toHaveValue('');
  await expect(options.getByRole('checkbox', { name: 'Tit For Tat', exact: true })).not.toBeChecked();
  await search.fill('cooperator');
  await options.getByRole('checkbox', { name: 'Cooperator', exact: true }).check();
  await search.fill('random');
  await expect(options.getByRole('checkbox', { name: 'Random', exact: true })).toBeChecked();
  await expect(page.locator('#opponent-filter-status')).toContainText('selected outside this filter');
  const accidentalRequest = page.waitForRequest('**/api/run/tournament', { timeout: 500 }).then(() => true).catch(() => false);
  await search.press('Enter');
  expect(await accidentalRequest).toBe(false);
  await page.route('**/api/run/tournament', route => route.fulfill({ contentType: 'application/x-ndjson', body: '{"type":"error","message":"Search selection captured."}\n' }));
  const submitted = page.waitForRequest('**/api/run/tournament');
  await page.getByRole('button', { name: 'Run simulation →' }).click();
  const { opponents } = (await submitted).postDataJSON();
  expect(opponents).toContain('Cooperator');
  expect(opponents).toContain('Random');
  expect(opponents).not.toContain('Tit For Tat');
  expect(opponents).toHaveLength(9);
  await expect(page.getByRole('alert')).toContainText('Search selection captured.');
});

test('uses readable mathematical names and retains canonical identifiers in requests and exports', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Run simulation →' })).toBeEnabled({ timeout: 60_000 });
  const search = page.getByRole('searchbox', { name: 'Filter opponents by name' });
  const options = page.getByRole('group', { name: 'Opponent options' });
  const names = [
    { query: 'phi', label: 'Golden ratio (φ)', id: '$\\phi$' },
    { query: 'π', label: 'Pi (π)', id: '$\\pi$' },
    { query: "Euler's", label: 'Euler’s number (e)', id: '$e$' },
  ];
  for (const { query, label } of names) {
    await search.fill(query);
    await options.getByRole('checkbox', { name: label, exact: true }).check();
  }
  await page.getByRole('button', { name: 'Clear filter' }).click();
  for (const { label } of names) await expect(options.getByRole('checkbox', { name: label, exact: true })).toBeChecked();
  const canonical = names.map(item => item.id);
  await page.route('**/api/run/tournament', route => {
    const config = route.request().postDataJSON();
    const result = { kind: 'tournament', config, leaderboard: canonical.map(Player => ({ Player, Mean: 3 })), players: canonical, scores: [[3], [3], [3]], payoff_matrix: [[3, 3, 3], [3, 3, 3], [3, 3, 3]], wins: [[0], [0], [0]] };
    return route.fulfill({ contentType: 'application/x-ndjson', body: JSON.stringify({ type: 'result', result }) + '\n' });
  });
  const submitted = page.waitForRequest('**/api/run/tournament');
  await page.getByRole('button', { name: 'Run simulation →' }).click();
  expect((await submitted).postDataJSON().opponents).toEqual(expect.arrayContaining(canonical));
  await expect(page.getByText('Run complete')).toBeVisible();
  const leaderboard = page.getByRole('region', { name: 'Simulation results' }).getByRole('table').first();
  for (const { label } of names) await expect(leaderboard.getByRole('cell', { name: label, exact: true })).toBeVisible();
  const saving = page.waitForEvent('download');
  await page.getByRole('button', { name: '↓ Results + settings' }).click();
  const path = await (await saving).path();
  const exported = JSON.parse(await readFile(path!, 'utf8'));
  expect(exported.config.opponents).toEqual(expect.arrayContaining(canonical));
  expect(exported.players).toEqual(canonical);
});
