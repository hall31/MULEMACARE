import type { KAnonymousValue } from "@/api/types";
import { t } from "@/i18n";
import { isAvailable, seriesMax, tierLabel } from "@/lib/kanon";
import { cn } from "@/lib/cn";
import { KValue } from "./kvalue";
import { Badge, Icon, ScrollRegion, TONE_FILL, type Tone } from "./ui";

export interface BarRow {
  key: string;
  label: string;
  /** Série affichée en barre (une seule échelle par graphique). */
  value: KAnonymousValue;
  /** Colonnes du tableau alternatif (la première est la série de la barre). */
  columns: { label: string; value: KAnonymousValue; format: (v: number) => string }[];
  tone: Tone;
  /** Pastille de statut (icône + mot) quand la ligne est un statut. */
  status?: string;
}

/**
 * Graphique sobre et accessible (contrat §5, §12) : barres horizontales décoratives (aria-hidden),
 * chaque valeur écrite en texte à côté, couleur sémantique ou neutre (jamais l'accent), cellule
 * masquée dite « Masqué » sans barre, et le même contenu en tableau dans « Voir le tableau ».
 */
export function BarChart({ id, title, rows, format, caption, level = 3 }: { id: string; title: string; rows: BarRow[]; format: (v: number) => string; caption?: string; level?: 3 | 4 }) {
  const Heading = level === 4 ? "h4" : "h3";
  const max = seriesMax(rows.map((r) => r.value));
  return (
    <figure className="m-0 flex flex-col gap-3" aria-labelledby={`${id}-titre`} data-testid={`chart-${id}`}>
      <figcaption className="flex flex-col gap-0.5">
        <Heading id={`${id}-titre`} className="font-display text-body font-semibold">
          {title}
        </Heading>
        {caption ? <span className="text-caption text-fg-2">{caption}</span> : null}
      </figcaption>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {rows.map((row) => {
          const width = isAvailable(row.value) && max > 0 ? Math.max(2, Math.round((row.value.value / max) * 100)) : 0;
          return (
            <li key={row.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1" data-testid="bar-row" data-key={row.key} data-status={row.value.status}>
              <span className="min-w-0 truncate font-medium">{row.status ? <Badge tone={row.tone}>{row.label}</Badge> : row.label}</span>
              <KValue value={row.value} format={format} className="text-right" />
              <div className="col-span-2 h-2 rounded-full bg-sunk" aria-hidden="true">
                {width > 0 ? <div data-slot="bar" className={cn("h-2 rounded-full", TONE_FILL[row.tone])} style={{ width: `${width}%` }} /> : null}
              </div>
            </li>
          );
        })}
      </ul>
      <details className="rounded-md border border-line">
        <summary className="flex min-h-12 cursor-pointer items-center gap-2 px-3 font-medium">
          <Icon name="table" />
          {t("chart.showTable")}
        </summary>
        <ScrollRegion label={t("chart.tableLabel", { title })}>
          <table className="w-full border-collapse text-dense">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr className="border-b border-line text-left text-fg-2">
                <th scope="col" className="px-3 py-2 font-medium">
                  {t("chart.itemCol")}
                </th>
                {rows[0]?.columns.map((c) => (
                  <th key={c.label} scope="col" className="px-3 py-2 text-right font-medium">
                    {c.label}
                  </th>
                ))}
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  {t("chart.tierCol")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-b border-line last:border-b-0">
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    {row.label}
                  </th>
                  {row.columns.map((c) => (
                    <td key={c.label} className="px-3 py-2 text-right">
                      <KValue value={c.value} format={c.format} />
                    </td>
                  ))}
                  <td className="px-3 py-2 text-right text-fg-2">{isAvailable(row.value) ? tierLabel(row.value.contributors) : t("kanon.masked")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </details>
    </figure>
  );
}
