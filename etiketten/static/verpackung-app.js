// <verpackung-app> – Verpackungsetiketten drucken (Name, Info, Röstdatum, Charge,
// MHD, QR-Code). Zweite Etikettenart neben <etiketten-app>, gleiche Produktliste.
//
//   <script type="module" src="…/verpackung-app.js"></script>
//   <verpackung-app api="/api"></verpackung-app>
//
// Attribute:
//   api      Basisadresse der JSON-API (Standard: /api), siehe docs/API.md
//   kaffee   Kaffee-ID, die beim Start gewählt wird (optional)
//   titel    Überschrift (Standard: „Verpackungsetikett“, leer = keine Überschrift)
//
// Aussehen über dieselben CSS-Variablen wie <etiketten-app> (etiketten-app.css).
// Die Kaffees und ihre Info werden in <etiketten-app> im Reiter „Produkte“ gepflegt.

import { apiAnfrage, deutschesDatum, el, heuteIso } from "./gemeinsam.js";

const CHARGE = /^r[öo]e?(\d{2})(\d{2})(\d{2})-(\d{2})$/i;

const VORLAGE = `
  <link rel="stylesheet" href="${new URL("etiketten-app.css", import.meta.url)}">
  <style>
    .vorschau img { width: 240px; }
    .info { margin: 14px 0 0; padding: 10px 12px; border-radius: var(--r);
            background: var(--akzent-hell); white-space: pre-line; font-size: .95rem; }
    .info--leer { background: none; border: 1px dashed var(--linie); color: var(--leise); }
    #charge { font-variant-numeric: tabular-nums; letter-spacing: .03em; width: 11em; }
    .charge-pruefung { min-height: 1.2em; }
    .charge-pruefung.gut { color: var(--gut); }
    .charge-pruefung.schlecht { color: var(--schlecht); }
  </style>
  <header class="kopf">
    <h1 id="titel"></h1>
    <button id="status" class="status status--laedt" type="button" title="Druckerstatus neu prüfen">
      <span class="punkt"></span><span id="status-text">Prüfe Drucker …</span>
    </button>
  </header>
  <p id="status-hinweis" class="hinweis" hidden></p>

  <div class="raster">
    <section class="karte">
      <h2><span class="nr">1</span> Kaffee</h2>
      <div id="kaffees" class="kacheln" role="radiogroup" aria-label="Kaffee"></div>
      <p id="info" class="info" hidden></p>
      <p id="kaffees-fehler" class="fehler" hidden></p>
    </section>

    <section class="karte">
      <h2><span class="nr">2</span> Charge &amp; Menge</h2>
      <div class="felder">
        <label><span>Charge</span>
          <input id="charge" autocomplete="off" spellcheck="false" maxlength="12" placeholder="Rö261012-01">
          <small id="charge-pruefung" class="charge-pruefung"></small>
        </label>
        <label><span>MHD <span id="mhd-art" class="marke">berechnet</span></span>
          <input id="mhd" type="date">
          <small>aus Röstdatum + Haltbarkeit</small>
        </label>
        <button id="mhd-reset" class="link" type="button" hidden>wieder berechnen</button>
      </div>
      <label class="menge-label" for="menge">Anzahl Etiketten</label>
      <div class="menge">
        <button type="button" data-schritt="-1" aria-label="weniger">−</button>
        <input id="menge" type="number" min="1" max="999" value="1" inputmode="numeric">
        <button type="button" data-schritt="1" aria-label="mehr">+</button>
        <span class="schnell">
          <button type="button" data-menge="1">1</button>
          <button type="button" data-menge="5">5</button>
          <button type="button" data-menge="10">10</button>
          <button type="button" data-menge="20">20</button>
        </span>
      </div>
    </section>

    <section class="karte karte--druck">
      <h2><span class="nr">3</span> Drucken</h2>
      <figure class="vorschau">
        <img id="vorschau-bild" alt="Vorschau des Verpackungsetiketts" hidden>
        <figcaption id="vorschau-text">Kaffee und Charge wählen für eine Vorschau</figcaption>
      </figure>
      <button id="drucken" class="drucken" type="button" disabled>Drucken</button>
      <p id="meldung" class="meldung" role="status" aria-live="polite"></p>
      <details class="werkzeuge">
        <summary>Werkzeuge</summary>
        <button id="testdruck" type="button">Testetikett in dieser Größe drucken</button>
        <button id="zpl-zeigen" type="button">ZPL anzeigen</button>
        <pre id="zpl" hidden></pre>
      </details>
    </section>
  </div>
`;

// Röstdatum (JJJJ-MM-TT) aus der Charge, oder null. Maßgeblich ist die Prüfung im Server.
function roestdatum(charge) {
  const t = CHARGE.exec(charge.trim());
  if (!t) return null;
  const iso = `20${t[1]}-${t[2]}-${t[3]}`;
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) || d.getMonth() + 1 !== Number(t[2]) || t[4] === "00" ? null : iso;
}

class VerpackungApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = VORLAGE;
    this.zustand = {
      kaffees: [],
      kaffee: null,
      mhdManuell: false,
      vorschauAktiv: true,
      vorschauNr: 0,
      vorschauUrl: null,
      vorschauSchluessel: "",
    };
    this.vorschauTimer = null;
    this.gestartet = false;
  }

  connectedCallback() {
    if (this.gestartet) return;
    this.gestartet = true;
    const titel = this.getAttribute("titel") ?? "Verpackungsetikett";
    this.$("titel").textContent = titel;
    this.$("titel").hidden = !titel;
    this.verdrahten();
    this.statusLaden();
    this.kaffeesLaden();
  }

  disconnectedCallback() {
    clearTimeout(this.vorschauTimer);
  }

  $(id) {
    return this.shadowRoot.getElementById(id);
  }

  alle(selektor) {
    return [...this.shadowRoot.querySelectorAll(selektor)];
  }

  get apiBasis() {
    return (this.getAttribute("api") || "/api").replace(/\/+$/, "");
  }

  api(pfad, daten, methode) {
    return apiAnfrage(this.apiBasis, pfad, daten, methode);
  }

  meldung(text, art = "") {
    const e = this.$("meldung");
    e.textContent = text;
    e.className = "meldung" + (art ? ` meldung--${art}` : "");
  }

  async statusLaden() {
    const knopf = this.$("status");
    knopf.className = "status status--laedt";
    this.$("status-text").textContent = "Prüfe Drucker …";
    try {
      const s = await this.api("/verpackung/status");
      this.zustand.vorschauAktiv = s.vorschau;
      knopf.className = "status " + (s.ok ? "status--ok" : "status--fehler");
      this.$("status-text").textContent = s.ok ? `${s.drucker_name} bereit` : `${s.drucker_name}: Problem`;
      const hinweis = this.$("status-hinweis");
      hinweis.hidden = s.ok;
      hinweis.textContent = s.ok ? "" : [s.drucker.meldung, s.drucker.hinweis].filter(Boolean).join("\n");
    } catch (e) {
      knopf.className = "status status--fehler";
      this.$("status-text").textContent = "Drucker: Problem";
      this.$("status-hinweis").hidden = false;
      this.$("status-hinweis").textContent = e.message;
    }
  }

  // --- Kaffee -------------------------------------------------------------------

  kaffeeDaten() {
    return this.zustand.kaffees.find((k) => k.id === this.zustand.kaffee) || null;
  }

  async kaffeesLaden() {
    const fehler = this.$("kaffees-fehler");
    try {
      this.zustand.kaffees = await this.api("/produkte");
      fehler.hidden = true;
    } catch (e) {
      fehler.hidden = false;
      fehler.textContent = e.message;
      return;
    }
    this.$("kaffees").replaceChildren(...this.zustand.kaffees.map((k) => {
      const b = el("button", { type: "button", className: "kachel", role: "radio", data: { id: k.id } },
        el("strong", { textContent: k.anzeigename }),
        el("small", { textContent: `${k.mhd_monate} Mon.${k.info ? "" : " · ohne Info"}` }));
      b.setAttribute("aria-checked", "false");
      b.addEventListener("click", () => this.kaffeeWaehlen(k.id));
      return b;
    }));
    const vorgabe = this.getAttribute("kaffee");
    if (vorgabe && this.zustand.kaffees.some((k) => k.id === vorgabe)) this.kaffeeWaehlen(vorgabe);
    else this.aktualisieren();
  }

  kaffeeWaehlen(id) {
    this.zustand.kaffee = id;
    for (const k of this.alle(".kachel")) k.setAttribute("aria-checked", String(k.dataset.id === id));
    const k = this.kaffeeDaten();
    const info = this.$("info");
    info.hidden = false;
    info.className = "info" + (k.info ? "" : " info--leer");
    info.textContent = k.info
      ? k.info.split("|").map((z) => z.trim()).join("\n")
      : "Keine Info hinterlegt. Pflege unter Etikettendruck → Produkte.";
    this.mhdBerechnen();
  }

  // --- Charge & MHD ----------------------------------------------------------------

  chargePruefen() {
    const text = this.$("charge").value.trim();
    const anzeige = this.$("charge-pruefung");
    const datum = roestdatum(text);
    if (!text) {
      anzeige.textContent = "";
      anzeige.className = "charge-pruefung";
    } else if (datum) {
      anzeige.textContent = `✓ geröstet am ${deutschesDatum(datum)}`;
      anzeige.className = "charge-pruefung gut";
    } else {
      anzeige.textContent = "Format RöJJMMTT-NN, z. B. Rö261012-01";
      anzeige.className = "charge-pruefung schlecht";
    }
    return datum;
  }

  async mhdBerechnen() {
    const datum = this.chargePruefen();
    if (this.zustand.mhdManuell || !this.zustand.kaffee || !datum) {
      if (!this.zustand.mhdManuell) this.$("mhd").value = "";
      this.aktualisieren();
      return;
    }
    try {
      const r = await this.api(`/mhd?kaffee=${encodeURIComponent(this.zustand.kaffee)}&abgepackt=${datum}`);
      this.$("mhd").value = r.mhd;
    } catch (e) {
      this.meldung(e.message, "fehler");
    }
    this.aktualisieren();
  }

  mhdManuell(an) {
    this.zustand.mhdManuell = an;
    const marke = this.$("mhd-art");
    marke.textContent = an ? "manuell" : "berechnet";
    marke.className = "marke" + (an ? " marke--manuell" : "");
    this.$("mhd-reset").hidden = !an;
  }

  menge() {
    const n = parseInt(this.$("menge").value, 10);
    return Number.isFinite(n) ? Math.min(999, Math.max(1, n)) : 1;
  }

  auftrag() {
    return { kaffee: this.zustand.kaffee, charge: this.$("charge").value.trim(),
             mhd: this.$("mhd").value, menge: this.menge() };
  }

  bereit() {
    return Boolean(this.kaffeeDaten() && roestdatum(this.$("charge").value) && this.$("mhd").value);
  }

  // --- Vorschau & Knopf ---------------------------------------------------------------

  aktualisieren() {
    const k = this.kaffeeDaten();
    const knopf = this.$("drucken");
    knopf.disabled = !this.bereit();
    if (!k) {
      knopf.textContent = "Drucken";
    } else if (!roestdatum(this.$("charge").value)) {
      knopf.textContent = "Charge eingeben";
    } else {
      knopf.textContent = `${this.menge()} × ${k.anzeigename} drucken`;
      knopf.append(el("small", { textContent: `Charge ${this.$("charge").value.trim()}` }));
    }
    clearTimeout(this.vorschauTimer);
    this.vorschauTimer = setTimeout(() => this.vorschauLaden(), 300);
    if (!this.$("zpl").hidden) this.zplZeigen();
  }

  async vorschauLaden() {
    const z = this.zustand;
    const bild = this.$("vorschau-bild");
    const text = this.$("vorschau-text");
    if (!this.bereit()) {
      bild.hidden = true;
      z.vorschauSchluessel = "";
      text.textContent = "Kaffee und Charge wählen für eine Vorschau";
      return;
    }
    if (!z.vorschauAktiv) {
      text.textContent = "Vorschau ist ausgeschaltet (config.toml).";
      return;
    }
    const a = this.auftrag();
    const schluessel = `${a.kaffee}|${a.charge}|${a.mhd}`;
    if (schluessel === z.vorschauSchluessel && !bild.hidden) return;
    const nr = ++z.vorschauNr;
    z.vorschauSchluessel = schluessel;
    text.textContent = "Vorschau wird geladen …";
    try {
      const antwort = await this.api("/verpackung/vorschau", a);
      const blob = await antwort.blob();
      if (nr !== z.vorschauNr) return;
      if (z.vorschauUrl) URL.revokeObjectURL(z.vorschauUrl);
      z.vorschauUrl = URL.createObjectURL(blob);
      bild.src = z.vorschauUrl;
      bild.hidden = false;
      text.textContent = "Vorschau (labelary.com) – maßgeblich ist der echte Druck.";
    } catch (e) {
      if (nr !== z.vorschauNr) return;
      z.vorschauSchluessel = "";
      bild.hidden = true;
      text.textContent = e.message;
    }
  }

  // --- Aktionen -----------------------------------------------------------------------

  async drucken() {
    const knopf = this.$("drucken");
    if (!this.bereit() || knopf.classList.contains("laeuft")) return;
    const n = this.menge();
    if (n > 30 && !confirm(`Wirklich ${n} Verpackungsetiketten drucken?`)) return;
    knopf.classList.add("laeuft");
    this.meldung("Sende an Drucker …");
    try {
      const r = await this.api("/verpackung/drucken", this.auftrag());
      this.meldung(r.meldung, "ok");
    } catch (e) {
      this.meldung(e.message, "fehler");
      this.statusLaden();
    } finally {
      knopf.classList.remove("laeuft");
    }
  }

  async testdruck() {
    if (!confirm("Testetikett in der Größe des Verpackungsetiketts drucken?")) return;
    this.meldung("Sende Testetikett …");
    try {
      const r = await this.api("/verpackung/testdruck", {});
      this.meldung(r.meldung, "ok");
    } catch (e) {
      this.meldung(e.message, "fehler");
    }
  }

  async zplZeigen() {
    const pre = this.$("zpl");
    pre.hidden = false;
    if (!this.bereit()) {
      pre.textContent = "Erst Kaffee und Charge wählen.";
      return;
    }
    try {
      pre.textContent = (await this.api("/verpackung/zpl", this.auftrag())).zpl;
    } catch (e) {
      pre.textContent = e.message;
    }
  }

  verdrahten() {
    const $ = (id) => this.$(id);
    // Vorbelegt mit „Rö“ und dem heutigen Datum, die laufende Nummer tippt man selbst.
    $("charge").value = `Rö${heuteIso().slice(2).replaceAll("-", "")}-`;
    $("charge").addEventListener("input", () => this.mhdBerechnen());
    $("mhd").addEventListener("input", () => { this.mhdManuell(true); this.aktualisieren(); });
    $("mhd-reset").addEventListener("click", () => { this.mhdManuell(false); this.mhdBerechnen(); });
    $("menge").addEventListener("input", () => this.aktualisieren());
    $("menge").addEventListener("change", () => { $("menge").value = this.menge(); this.aktualisieren(); });
    for (const b of this.alle("[data-schritt]")) {
      b.addEventListener("click", () => {
        $("menge").value = Math.min(999, Math.max(1, this.menge() + Number(b.dataset.schritt)));
        this.aktualisieren();
      });
    }
    for (const b of this.alle("[data-menge]")) {
      b.addEventListener("click", () => { $("menge").value = b.dataset.menge; this.aktualisieren(); });
    }
    $("drucken").addEventListener("click", () => this.drucken());
    $("testdruck").addEventListener("click", () => this.testdruck());
    $("zpl-zeigen").addEventListener("click", () => this.zplZeigen());
    $("status").addEventListener("click", () => this.statusLaden());
  }
}

if (!customElements.get("verpackung-app")) customElements.define("verpackung-app", VerpackungApp);
