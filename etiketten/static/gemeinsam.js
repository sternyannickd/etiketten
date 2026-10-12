// Gemeinsame Hilfen für <etiketten-app> und <verpackung-app>.

export function heuteIso() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

export function deutschesDatum(iso) {
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}

export function el(tag, eigenschaften = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, w] of Object.entries(eigenschaften)) {
    if (k === "data") Object.assign(e.dataset, w);
    else if (k in e) e[k] = w;
    else e.setAttribute(k, w);
  }
  e.append(...kinder.filter((k) => k !== null && k !== undefined));
  return e;
}

// Anfrage an die JSON-API. Schreibende Anfragen tragen das CSRF-Token der
// einbindenden Seite (<meta name="csrf-token">), wenn es eines gibt (Portal tosto).
// Antworten, die kein JSON sind (Vorschau-PNG), kommen als Response zurück.
export async function apiAnfrage(basis, pfad, daten, methode) {
  const optionen = { headers: {} };
  if (daten !== undefined) {
    optionen.method = methode || "POST";
    optionen.headers["Content-Type"] = "application/json";
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (token) optionen.headers["X-CSRF-Token"] = token;
    optionen.body = JSON.stringify(daten);
  }
  const antwort = await fetch(basis + pfad, optionen);
  if (antwort.status === 401) throw new Error("Sitzung abgelaufen – bitte neu anmelden. Die Eingaben bleiben erhalten.");
  const typ = antwort.headers.get("Content-Type") || "";
  if (!typ.includes("application/json")) {
    if (!antwort.ok) throw new Error(`Serverfehler ${antwort.status}`);
    return antwort;
  }
  const json = await antwort.json();
  if (!antwort.ok || json.ok === false) throw new Error(json.fehler || `Serverfehler ${antwort.status}`);
  return json;
}
