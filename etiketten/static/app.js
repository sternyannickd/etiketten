"use strict";

const $ = (id) => document.getElementById(id);

const zustand = {
  produkte: [],
  produkt: null,        // gewählte Produkt-ID
  mhdManuell: false,
  vorschauAktiv: true,
  vorschauNr: 0,        // verwirft veraltete Vorschau-Antworten
  vorschauUrl: null,
  vorschauSchluessel: "", // Produkt + MHD der angezeigten Vorschau (Menge ändert sie nicht)
};

function heuteIso() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

function deutschesDatum(iso) {
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}

async function api(pfad, daten) {
  const optionen = daten === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  };
  const antwort = await fetch(pfad, optionen);
  const typ = antwort.headers.get("Content-Type") || "";
  if (!typ.includes("application/json")) {
    if (!antwort.ok) throw new Error(`Serverfehler ${antwort.status}`);
    return antwort;
  }
  const json = await antwort.json();
  if (!antwort.ok || json.ok === false) throw new Error(json.fehler || `Serverfehler ${antwort.status}`);
  return json;
}

function auftrag() {
  return { produkt: zustand.produkt, mhd: $("mhd").value, menge: menge() };
}

function menge() {
  const n = parseInt($("menge").value, 10);
  return Number.isFinite(n) ? Math.min(999, Math.max(1, n)) : 1;
}

function meldung(text, art = "") {
  const el = $("meldung");
  el.textContent = text;
  el.className = "meldung" + (art ? ` meldung--${art}` : "");
}

// --- Status -------------------------------------------------------------------

async function statusLaden() {
  const knopf = $("status");
  knopf.className = "status status--laedt";
  $("status-text").textContent = "Prüfe Drucker …";
  try {
    const s = await api("/api/status");
    zustand.vorschauAktiv = s.vorschau;
    const ok = s.drucker.ok;
    knopf.className = "status " + (ok ? "status--ok" : "status--fehler");
    $("status-text").textContent = ok ? `${s.drucker_name} bereit` : `${s.drucker_name}: Problem`;
    const hinweis = $("status-hinweis");
    hinweis.hidden = ok;
    hinweis.textContent = ok ? "" : [s.drucker.meldung, s.drucker.hinweis].filter(Boolean).join("\n");
  } catch (e) {
    knopf.className = "status status--fehler";
    $("status-text").textContent = "Server nicht erreichbar";
  }
}

// --- Produkte -----------------------------------------------------------------

async function produkteLaden() {
  try {
    zustand.produkte = await api("/api/produkte");
  } catch (e) {
    const f = $("produkte-fehler");
    f.hidden = false;
    f.textContent = e.message;
    return;
  }
  const liste = $("produkte");
  liste.replaceChildren(...zustand.produkte.map((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "kachel";
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", "false");
    b.dataset.id = p.id;
    const name = document.createElement("strong");
    name.textContent = p.name;
    const ean = document.createElement("small");
    ean.textContent = `${p.gtin} · ${p.mhd_monate} Mon.`;
    b.append(name, ean);
    b.addEventListener("click", () => produktWaehlen(p.id));
    return b;
  }));
  // Direktlink auf ein Produkt, z. B. http://localhost:8077/?produkt=kolumbien
  const vorgabe = new URLSearchParams(location.search).get("produkt");
  if (vorgabe && zustand.produkte.some((p) => p.id === vorgabe)) produktWaehlen(vorgabe);
}

function produktWaehlen(id) {
  zustand.produkt = id;
  for (const k of document.querySelectorAll(".kachel")) {
    k.setAttribute("aria-checked", String(k.dataset.id === id));
  }
  $("drucken").disabled = false;
  if (zustand.mhdManuell) {
    aktualisieren();
  } else {
    mhdBerechnen();
  }
}

// --- MHD ----------------------------------------------------------------------

async function mhdBerechnen() {
  if (!zustand.produkt) return;
  const abgepackt = $("abgepackt").value || heuteIso();
  try {
    const r = await api(`/api/mhd?produkt=${encodeURIComponent(zustand.produkt)}&abgepackt=${abgepackt}`);
    $("mhd").value = r.mhd;
  } catch (e) {
    meldung(e.message, "fehler");
  }
  aktualisieren();
}

function mhdManuell(an) {
  zustand.mhdManuell = an;
  const marke = $("mhd-art");
  marke.textContent = an ? "manuell" : "berechnet";
  marke.className = "marke" + (an ? " marke--manuell" : "");
  $("mhd-reset").hidden = !an;
}

// --- Vorschau & Knopf ------------------------------------------------------------

let vorschauTimer = null;

function aktualisieren() {
  const p = zustand.produkte.find((x) => x.id === zustand.produkt);
  const n = menge();
  const knopf = $("drucken");
  knopf.textContent = p ? `${n} × ${p.name} drucken` : "Drucken";
  if (p && $("mhd").value) {
    const zusatz = document.createElement("small");
    zusatz.textContent = `MHD: ${deutschesDatum($("mhd").value)}`;
    knopf.append(zusatz);
  }
  clearTimeout(vorschauTimer);
  vorschauTimer = setTimeout(vorschauLaden, 250);
  if (!$("zpl").hidden) zplZeigen();
}

async function vorschauLaden() {
  const bild = $("vorschau-bild");
  const text = $("vorschau-text");
  if (!zustand.produkt || !$("mhd").value) return;
  if (!zustand.vorschauAktiv) {
    text.textContent = "Vorschau ist ausgeschaltet (config.toml).";
    return;
  }
  const schluessel = `${zustand.produkt}|${$("mhd").value}`;
  if (schluessel === zustand.vorschauSchluessel && !bild.hidden) return;
  const nr = ++zustand.vorschauNr;
  zustand.vorschauSchluessel = schluessel;
  text.textContent = "Vorschau wird geladen …";
  try {
    const antwort = await api("/api/vorschau", auftrag());
    const blob = await antwort.blob();
    if (nr !== zustand.vorschauNr) return;
    if (zustand.vorschauUrl) URL.revokeObjectURL(zustand.vorschauUrl);
    zustand.vorschauUrl = URL.createObjectURL(blob);
    bild.src = zustand.vorschauUrl;
    bild.hidden = false;
    text.textContent = "Vorschau (labelary.com) – maßgeblich ist der echte Druck.";
  } catch (e) {
    if (nr !== zustand.vorschauNr) return;
    zustand.vorschauSchluessel = "";
    bild.hidden = true;
    text.textContent = `${e.message} – Drucken funktioniert trotzdem.`;
  }
}

// --- Aktionen -----------------------------------------------------------------

async function drucken() {
  const knopf = $("drucken");
  if (!zustand.produkt || knopf.classList.contains("laeuft")) return;
  const n = menge();
  if (n > 50 && !confirm(`Wirklich ${n} Etiketten drucken?`)) return;
  knopf.classList.add("laeuft");
  meldung("Sende an Drucker …");
  try {
    const r = await api("/api/drucken", auftrag());
    meldung(r.meldung, "ok");
  } catch (e) {
    meldung(e.message, "fehler");
    statusLaden();
  } finally {
    knopf.classList.remove("laeuft");
  }
}

async function testdruck() {
  if (!confirm("Testetikett drucken?")) return;
  meldung("Sende Testetikett …");
  try {
    const r = await api("/api/testdruck", {});
    meldung(r.meldung, "ok");
  } catch (e) {
    meldung(e.message, "fehler");
  }
}

async function zplZeigen() {
  const pre = $("zpl");
  pre.hidden = false;
  if (!zustand.produkt) {
    pre.textContent = "Erst ein Produkt wählen.";
    return;
  }
  try {
    pre.textContent = (await api("/api/zpl", auftrag())).zpl;
  } catch (e) {
    pre.textContent = e.message;
  }
}

// --- Start --------------------------------------------------------------------

function verdrahten() {
  $("abgepackt").value = heuteIso();
  $("abgepackt").addEventListener("change", () => { if (!zustand.mhdManuell) mhdBerechnen(); });
  $("mhd").addEventListener("input", () => { mhdManuell(true); aktualisieren(); });
  $("mhd-reset").addEventListener("click", () => { mhdManuell(false); mhdBerechnen(); });
  $("menge").addEventListener("input", aktualisieren);
  $("menge").addEventListener("change", () => { $("menge").value = menge(); aktualisieren(); });
  for (const b of document.querySelectorAll("[data-schritt]")) {
    b.addEventListener("click", () => {
      $("menge").value = Math.min(999, Math.max(1, menge() + Number(b.dataset.schritt)));
      aktualisieren();
    });
  }
  for (const b of document.querySelectorAll("[data-menge]")) {
    b.addEventListener("click", () => { $("menge").value = b.dataset.menge; aktualisieren(); });
  }
  $("drucken").addEventListener("click", drucken);
  $("testdruck").addEventListener("click", testdruck);
  $("zpl-zeigen").addEventListener("click", zplZeigen);
  $("status").addEventListener("click", statusLaden);
}

verdrahten();
statusLaden();
produkteLaden();
