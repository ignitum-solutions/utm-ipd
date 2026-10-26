/** Display names only. Configurations and exports retain Axelrod's identifiers. */
const MATHEMATICAL_NAMES: Record<string, { label: string; aliases: string }> = {
  "$\\phi$": { label: "Golden ratio (φ)", aliases: "golden phi" },
  "$\\pi$": { label: "Pi (π)", aliases: "pi" },
  $e$: { label: "Euler’s number (e)", aliases: "euler eulers" },
};

export function opponentLabel(name: string): string {
  return MATHEMATICAL_NAMES[name]?.label ?? name;
}

export function matchesOpponent(name: string, query: string): boolean {
  const normalize = (value: string) =>
    value
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("en")
      .replace(/[^\p{L}\p{N}]+/gu, " ")
      .trim();
  const searchable = normalize(
    `${name} ${opponentLabel(name)} ${MATHEMATICAL_NAMES[name]?.aliases ?? ""}`,
  );
  return normalize(query)
    .split(/\s+/)
    .every((term) => searchable.includes(term));
}
