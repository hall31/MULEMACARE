import { encode } from "uqr";

/**
 * Matrice du QR de la carte (uqr, MIT, portage de l'encodeur de référence de Nayuki) et tracé
 * SVG compact : une bande par suite de modules foncés sur une ligne. La couleur vient des
 * jetons, en CSS (`.qr-m`) ; jamais dans le tracé.
 *
 * Correction d'erreur M (15 %) : un écran rayé ou un reflet au comptoir ne bloque pas la lecture.
 */
export interface QrModules {
  size: number;
  path: string;
  dark: ReadonlySet<string>;
}

export function qrModules(payload: string): QrModules {
  const qr = encode(payload, { ecc: "M", border: 0 });
  const dark = new Set<string>();
  let path = "";
  qr.data.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      if (!row[x]) {
        x += 1;
        continue;
      }
      const start = x;
      while (x < row.length && row[x]) {
        dark.add(`${x},${y}`);
        x += 1;
      }
      const run = x - start;
      path += `M${start} ${y}h${run}v1h-${run}z`;
    }
  });
  return { size: qr.size, path, dark };
}
