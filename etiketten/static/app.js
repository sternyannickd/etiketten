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
  bearbeitet: null,     // Produkt-ID im Bearbeiten-Dialog, null = neues Produkt
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
    const texte = [...(s.warnungen || [])];
    if (!ok) texte.push(s.drucker.meldung, s.drucker.hinweis);
    const hinweis = $("status-hinweis");
    hinweis.textContent = texte.filter(Boolean).join("\n");
    hinweis.hidden = !hinweis.textContent;
    $("version").textContent = `Version ${s.version} · Daten: ${s.daten_ordner}`;
  } catch (e) {
    knopf.className = "status status--fehler";
    $("status-text").textContent = "Server nicht erreichbar";
  }
}

// --- Produkte -----------------------------------------------------------------

async function produkteLaden(auswahl) {
  const f = $("produkte-fehler");
  try {
    zustand.produkte = await api("/api/produkte");
    f.hidden = true;
  } catch (e) {
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
  const vorgabe = auswahl !== undefined ? auswahl : new URLSearchParams(location.search).get("produkt");
  if (vorgabe && zustand.produkte.some((p) => p.id === vorgabe)) {
    produktWaehlen(vorgabe);
  } else if (auswahl !== undefined) {
    zustand.produkt = null;
    $("drucken").disabled = true;
    $("produkt-bearbeiten").hidden = true;
    aktualisieren();
  }
}

// --- Produkte bearbeiten -----------------------------------------------------------

function eanFehler(gtin) {
  if (!/^\d{13}$/.test(gtin)) return gtin.length ? `${gtin.length} von 13 Ziffern` : "13 Ziffern eingeben";
  const summe = [...gtin.slice(0, 12)].reduce((s, z, i) => s + Number(z) * (i % 2 ? 3 : 1), 0);
  const soll = (10 - (summe % 10)) % 10;
  return Number(gtin[12]) === soll ? "" : `Prüfziffer falsch – müsste ${soll} sein. Tippfehler?`;
}

function eanPruefen() {
  const feld = $("p-gtin");
  feld.value = feld.value.replace(/\D/g, "");
  const fehler = eanFehler(feld.value);
  const hinweis = $("p-gtin-hinweis");
  hinweis.textContent = fehler || "EAN gültig";
  hinweis.className = feld.value.length === 13 ? (fehler ? "schlecht" : "gut") : "";
  feld.setAttribute("aria-invalid", String(feld.value.length === 13 && !!fehler));
  return !fehler;
}

function dialogOeffnen(produkt) {
  zustand.bearbeitet = produkt ? produkt.id : null;
  $("produkt-titel").textContent = produkt ? "Produkt bearbeiten" : "Neues Produkt";
  $("p-name").value = produkt ? produkt.etikett_name : "";
  $("p-gtin").value = produkt ? produkt.gtin : "";
  $("p-monate").value = produkt ? produkt.mhd_monate : 12;
  $("p-loeschen").hidden = !produkt;
  $("p-fehler").hidden = true;
  eanPruefen();
  if (!produkt) $("p-gtin-hinweis").textContent = "Die letzte Ziffer ist die Prüfziffer – Tippfehler fallen sofort auf.";
  $("produkt-dialog").showModal();
  $("p-name").focus();
}

function dialogFehler(text) {
  const f = $("p-fehler");
  f.textContent = text;
  f.hidden = false;
}

async function produktSpeichern(ereignis) {
  ereignis.preventDefault();
  const name = $("p-name").value.trim();
  if (!name) return dialogFehler("Bitte einen Namen eingeben.");
  if (!eanPruefen()) return dialogFehler(`EAN: ${eanFehler($("p-gtin").value)}`);
  try {
    const r = await api("/api/produkt/speichern", {
      alte_id: zustand.bearbeitet, name, gtin: $("p-gtin").value,
      mhd_monate: $("p-monate").value,
    });
    $("produkt-dialog").close();
    zustand.vorschauSchluessel = "";
    await produkteLaden(r.produkt.id);
    meldung(`„${r.produkt.name}“ gespeichert.`, "ok");
  } catch (e) {
    dialogFehler(e.message);
  }
}

async function produktLoeschen() {
  const p = zustand.produkte.find((x) => x.id === zustand.bearbeitet);
  if (!p || !confirm(`„${p.name}“ wirklich löschen?`)) return;
  try {
    await api("/api/produkt/loeschen", { id: p.id });
    $("produkt-dialog").close();
    await produkteLaden(null);
    meldung(`„${p.name}“ gelöscht.`, "ok");
  } catch (e) {
    dialogFehler(e.message);
  }
}

function produktWaehlen(id) {
  zustand.produkt = id;
  for (const k of document.querySelectorAll(".kachel")) {
    k.setAttribute("aria-checked", String(k.dataset.id === id));
  }
  $("drucken").disabled = false;
  $("produkt-bearbeiten").hidden = false;
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

async function ordnerOeffnen() {
  try {
    await api("/api/ordner", {});
  } catch (e) {
    meldung(e.message, "fehler");
  }
}

async function beenden() {
  if (!confirm("Programm beenden? Zum erneuten Starten das Programm wieder öffnen.")) return;
  try {
    await api("/api/beenden", {});
  } catch (e) {
    // Der Server ist schon weg – das ist hier gewollt.
  }
  document.body.innerHTML = "<main class=\"karte\" style=\"max-width:480px;margin:40px auto\">" +
    "<h1>Etikettendruck beendet</h1><p>Dieses Fenster kann geschlossen werden. " +
    "Zum erneuten Starten das Programm wieder öffnen.</p></main>";
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
  $("ordner").addEventListener("click", ordnerOeffnen);
  $("beenden").addEventListener("click", beenden);
  $("produkt-neu").addEventListener("click", () => dialogOeffnen(null));
  $("produkt-bearbeiten").addEventListener("click", () => {
    dialogOeffnen(zustand.produkte.find((p) => p.id === zustand.produkt));
  });
  $("produkt-form").addEventListener("submit", produktSpeichern);
  $("p-gtin").addEventListener("input", eanPruefen);
  $("p-abbrechen").addEventListener("click", () => $("produkt-dialog").close());
  $("p-loeschen").addEventListener("click", produktLoeschen);
}

verdrahten();
statusLaden();
produkteLaden();
