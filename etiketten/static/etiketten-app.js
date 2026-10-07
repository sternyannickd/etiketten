// <etiketten-app> – die Oberfläche als Web Component, einbindbar in jede Seite.
//
//   <script type="module" src="…/etiketten-app.js"></script>
//   <etiketten-app api="/api"></etiketten-app>
//
// Attribute:
//   api      Basisadresse der JSON-API (Standard: /api)
//   produkt  Produkt-ID, die beim Start gewählt wird (optional)
//   titel    Überschrift (Standard: „Etikettendruck“, leer = keine Überschrift)
//
// Das Aussehen passt sich über CSS-Variablen der einbindenden Seite an
// (--farbe-akzent, --schrift, --radius …), siehe etiketten-app.css.

const VORLAGE = `
  <link rel="stylesheet" href="${new URL("etiketten-app.css", import.meta.url)}">
  <header class="kopf">
    <h1 id="titel"></h1>
    <button id="status" class="status status--laedt" type="button" title="Druckerstatus neu prüfen">
      <span class="punkt"></span><span id="status-text">Prüfe Drucker …</span>
    </button>
  </header>
  <p id="status-hinweis" class="hinweis" hidden></p>

  <div class="raster">
    <section class="karte">
      <h2><span class="nr">1</span> Produkt</h2>
      <div id="produkte" class="kacheln" role="radiogroup" aria-label="Produkt"></div>
      <p id="produkte-fehler" class="fehler" hidden></p>
    </section>

    <section class="karte">
      <h2><span class="nr">2</span> Datum &amp; Menge</h2>
      <div class="felder">
        <label><span>Abgepackt am</span>
          <input id="abgepackt" type="date">
        </label>
        <label><span>MHD <span id="mhd-art" class="marke">berechnet</span></span>
          <input id="mhd" type="date">
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
          <button type="button" data-menge="6">6</button>
          <button type="button" data-menge="12">12</button>
          <button type="button" data-menge="24">24</button>
        </span>
      </div>
    </section>

    <section class="karte karte--druck">
      <h2><span class="nr">3</span> Drucken</h2>
      <figure class="vorschau">
        <img id="vorschau-bild" alt="Vorschau des Etiketts" hidden>
        <figcaption id="vorschau-text">Produkt wählen für eine Vorschau</figcaption>
      </figure>
      <button id="drucken" class="drucken" type="button" disabled>Drucken</button>
      <p id="meldung" class="meldung" role="status" aria-live="polite"></p>
      <details class="werkzeuge">
        <summary>Werkzeuge</summary>
        <button id="testdruck" type="button">Testetikett drucken (Kalibrierung &amp; Umlaute)</button>
        <button id="zpl-zeigen" type="button">ZPL anzeigen</button>
        <pre id="zpl" hidden></pre>
      </details>
    </section>
  </div>
`;

function heuteIso() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

function deutschesDatum(iso) {
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}

class EtikettenApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = VORLAGE;
    this.zustand = {
      produkte: [],
      produkt: null,        // gewählte Produkt-ID
      mhdManuell: false,
      vorschauAktiv: true,
      vorschauNr: 0,        // verwirft veraltete Vorschau-Antworten
      vorschauUrl: null,
      vorschauSchluessel: "", // Produkt + MHD der angezeigten Vorschau (Menge ändert sie nicht)
    };
    this.vorschauTimer = null;
    this.gestartet = false;
  }

  connectedCallback() {
    if (this.gestartet) return;  // beim Verschieben im DOM nicht doppelt starten
    this.gestartet = true;
    const titel = this.getAttribute("titel") ?? "Etikettendruck";
    this.$("titel").textContent = titel;
    this.$("titel").hidden = !titel;
    this.verdrahten();
    this.statusLaden();
    this.produkteLaden();
  }

  disconnectedCallback() {
    clearTimeout(this.vorschauTimer);
  }

  $(id) {
    return this.shadowRoot.getElementById(id);
  }

  get apiBasis() {
    return (this.getAttribute("api") || "/api").replace(/\/+$/, "");
  }

  async api(pfad, daten) {
    const optionen = daten === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(daten),
    };
    const antwort = await fetch(this.apiBasis + pfad, optionen);
    const typ = antwort.headers.get("Content-Type") || "";
    if (!typ.includes("application/json")) {
      if (!antwort.ok) throw new Error(`Serverfehler ${antwort.status}`);
      return antwort;
    }
    const json = await antwort.json();
    if (!antwort.ok || json.ok === false) throw new Error(json.fehler || `Serverfehler ${antwort.status}`);
    return json;
  }

  auftrag() {
    return { produkt: this.zustand.produkt, mhd: this.$("mhd").value, menge: this.menge() };
  }

  menge() {
    const n = parseInt(this.$("menge").value, 10);
    return Number.isFinite(n) ? Math.min(999, Math.max(1, n)) : 1;
  }

  meldung(text, art = "") {
    const el = this.$("meldung");
    el.textContent = text;
    el.className = "meldung" + (art ? ` meldung--${art}` : "");
  }

  // --- Status -----------------------------------------------------------------

  async statusLaden() {
    const knopf = this.$("status");
    knopf.className = "status status--laedt";
    this.$("status-text").textContent = "Prüfe Drucker …";
    try {
      const s = await this.api("/status");
      this.zustand.vorschauAktiv = s.vorschau;
      const ok = s.drucker.ok;
      knopf.className = "status " + (ok ? "status--ok" : "status--fehler");
      this.$("status-text").textContent = ok ? `${s.drucker_name} bereit` : `${s.drucker_name}: Problem`;
      const hinweis = this.$("status-hinweis");
      hinweis.hidden = ok;
      hinweis.textContent = ok ? "" : [s.drucker.meldung, s.drucker.hinweis].filter(Boolean).join("\n");
    } catch (e) {
      knopf.className = "status status--fehler";
      this.$("status-text").textContent = "Server nicht erreichbar";
    }
  }

  // --- Produkte ---------------------------------------------------------------

  async produkteLaden() {
    try {
      this.zustand.produkte = await this.api("/produkte");
    } catch (e) {
      const f = this.$("produkte-fehler");
      f.hidden = false;
      f.textContent = e.message;
      return;
    }
    this.$("produkte").replaceChildren(...this.zustand.produkte.map((p) => {
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
      b.addEventListener("click", () => this.produktWaehlen(p.id));
      return b;
    }));
    const vorgabe = this.getAttribute("produkt");
    if (vorgabe && this.zustand.produkte.some((p) => p.id === vorgabe)) this.produktWaehlen(vorgabe);
  }

  produktWaehlen(id) {
    this.zustand.produkt = id;
    for (const k of this.shadowRoot.querySelectorAll(".kachel")) {
      k.setAttribute("aria-checked", String(k.dataset.id === id));
    }
    this.$("drucken").disabled = false;
    if (this.zustand.mhdManuell) {
      this.aktualisieren();
    } else {
      this.mhdBerechnen();
    }
  }

  // --- MHD --------------------------------------------------------------------

  async mhdBerechnen() {
    if (!this.zustand.produkt) return;
    const abgepackt = this.$("abgepackt").value || heuteIso();
    try {
      const r = await this.api(`/mhd?produkt=${encodeURIComponent(this.zustand.produkt)}&abgepackt=${abgepackt}`);
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

  // --- Vorschau & Knopf -------------------------------------------------------

  aktualisieren() {
    const p = this.zustand.produkte.find((x) => x.id === this.zustand.produkt);
    const n = this.menge();
    const knopf = this.$("drucken");
    knopf.textContent = p ? `${n} × ${p.name} drucken` : "Drucken";
    if (p && this.$("mhd").value) {
      const zusatz = document.createElement("small");
      zusatz.textContent = `MHD: ${deutschesDatum(this.$("mhd").value)}`;
      knopf.append(zusatz);
    }
    clearTimeout(this.vorschauTimer);
    this.vorschauTimer = setTimeout(() => this.vorschauLaden(), 250);
    if (!this.$("zpl").hidden) this.zplZeigen();
  }

  async vorschauLaden() {
    const z = this.zustand;
    const bild = this.$("vorschau-bild");
    const text = this.$("vorschau-text");
    if (!z.produkt || !this.$("mhd").value) return;
    if (!z.vorschauAktiv) {
      text.textContent = "Vorschau ist ausgeschaltet (config.toml).";
      return;
    }
    const schluessel = `${z.produkt}|${this.$("mhd").value}`;
    if (schluessel === z.vorschauSchluessel && !bild.hidden) return;
    const nr = ++z.vorschauNr;
    z.vorschauSchluessel = schluessel;
    text.textContent = "Vorschau wird geladen …";
    try {
      const antwort = await this.api("/vorschau", this.auftrag());
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
      text.textContent = `${e.message} – Drucken funktioniert trotzdem.`;
    }
  }

  // --- Aktionen ---------------------------------------------------------------

  async drucken() {
    const knopf = this.$("drucken");
    if (!this.zustand.produkt || knopf.classList.contains("laeuft")) return;
    const n = this.menge();
    if (n > 50 && !confirm(`Wirklich ${n} Etiketten drucken?`)) return;
    knopf.classList.add("laeuft");
    this.meldung("Sende an Drucker …");
    try {
      const r = await this.api("/drucken", this.auftrag());
      this.meldung(r.meldung, "ok");
    } catch (e) {
      this.meldung(e.message, "fehler");
      this.statusLaden();
    } finally {
      knopf.classList.remove("laeuft");
    }
  }

  async testdruck() {
    if (!confirm("Testetikett drucken?")) return;
    this.meldung("Sende Testetikett …");
    try {
      const r = await this.api("/testdruck", {});
      this.meldung(r.meldung, "ok");
    } catch (e) {
      this.meldung(e.message, "fehler");
    }
  }

  async zplZeigen() {
    const pre = this.$("zpl");
    pre.hidden = false;
    if (!this.zustand.produkt) {
      pre.textContent = "Erst ein Produkt wählen.";
      return;
    }
    try {
      pre.textContent = (await this.api("/zpl", this.auftrag())).zpl;
    } catch (e) {
      pre.textContent = e.message;
    }
  }

  // --- Start ------------------------------------------------------------------

  verdrahten() {
    const $ = (id) => this.$(id);
    $("abgepackt").value = heuteIso();
    $("abgepackt").addEventListener("change", () => { if (!this.zustand.mhdManuell) this.mhdBerechnen(); });
    $("mhd").addEventListener("input", () => { this.mhdManuell(true); this.aktualisieren(); });
    $("mhd-reset").addEventListener("click", () => { this.mhdManuell(false); this.mhdBerechnen(); });
    $("menge").addEventListener("input", () => this.aktualisieren());
    $("menge").addEventListener("change", () => { $("menge").value = this.menge(); this.aktualisieren(); });
    for (const b of this.shadowRoot.querySelectorAll("[data-schritt]")) {
      b.addEventListener("click", () => {
        $("menge").value = Math.min(999, Math.max(1, this.menge() + Number(b.dataset.schritt)));
        this.aktualisieren();
      });
    }
    for (const b of this.shadowRoot.querySelectorAll("[data-menge]")) {
      b.addEventListener("click", () => { $("menge").value = b.dataset.menge; this.aktualisieren(); });
    }
    $("drucken").addEventListener("click", () => this.drucken());
    $("testdruck").addEventListener("click", () => this.testdruck());
    $("zpl-zeigen").addEventListener("click", () => this.zplZeigen());
    $("status").addEventListener("click", () => this.statusLaden());
  }
}

if (!customElements.get("etiketten-app")) customElements.define("etiketten-app", EtikettenApp);
