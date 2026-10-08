// <etiketten-app> – die Oberfläche als Web Component, einbindbar in jede Seite.
//
//   <script type="module" src="…/etiketten-app.js"></script>
//   <etiketten-app api="/api"></etiketten-app>
//
// Attribute:
//   api      Basisadresse der JSON-API (Standard: /api), siehe docs/API.md
//   kaffee   Kaffee-ID, die beim Start gewählt wird (optional)
//   version  Versions-ID dazu (optional)
//   titel    Überschrift (Standard: „Etikettendruck“, leer = keine Überschrift)
//
// Das Aussehen passt sich über CSS-Variablen der einbindenden Seite an
// (--farbe-akzent, --schrift, --radius …), siehe etiketten-app.css.

const VORLAGE = `
  <link rel="stylesheet" href="${new URL("etiketten-app.css", import.meta.url)}">
  <header class="kopf">
    <h1 id="titel"></h1>
    <nav id="reiter" class="reiter" hidden>
      <button type="button" data-ansicht="drucken" aria-pressed="true">Drucken</button>
      <button type="button" data-ansicht="produkte" aria-pressed="false">Produkte</button>
    </nav>
    <button id="status" class="status status--laedt" type="button" title="Druckerstatus neu prüfen">
      <span class="punkt"></span><span id="status-text">Prüfe Drucker …</span>
    </button>
  </header>
  <p id="status-hinweis" class="hinweis" hidden></p>

  <div id="ansicht-drucken" class="raster">
    <section class="karte">
      <h2><span class="nr">1</span> Kaffee</h2>
      <div id="kaffees" class="kacheln" role="radiogroup" aria-label="Kaffee"></div>
      <div id="versionen-feld" class="versionen-wahl" hidden>
        <span class="unterzeile">Version</span>
        <div id="versionen" class="chips" role="radiogroup" aria-label="Version"></div>
      </div>
      <p id="kaffees-fehler" class="fehler" hidden></p>
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
        <figcaption id="vorschau-text">Kaffee wählen für eine Vorschau</figcaption>
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

  <div id="ansicht-produkte" class="verwaltung" hidden>
    <section class="karte">
      <div class="liste-kopf">
        <h2>Kaffees</h2>
        <button id="neu" type="button" class="knopf">+ Neuer Kaffee</button>
      </div>
      <label class="haken"><input id="archiv-zeigen" type="checkbox"> Archivierte zeigen</label>
      <ul id="kaffee-liste" class="kaffee-liste"></ul>
      <p id="liste-fehler" class="fehler" hidden></p>
    </section>

    <section class="karte">
      <p id="formular-leer" class="leise">Kaffee in der Liste wählen oder neu anlegen.</p>
      <form id="formular" hidden novalidate>
        <h2 id="formular-titel"></h2>
        <div class="felder">
          <label class="breit"><span>Name auf dem Etikett</span>
            <input id="f-name" maxlength="60" autocomplete="off">
            <small>„|“ erzwingt einen Zeilenumbruch, z. B. Espresso|Guatemala</small>
          </label>
          <label><span>Haltbarkeit (Monate)</span>
            <input id="f-monate" type="number" min="1" max="60" inputmode="numeric">
          </label>
        </div>
        <label id="f-archiv-zeile" class="haken">
          <input id="f-archiviert" type="checkbox"> Kaffee archivieren (wird nicht mehr zum Drucken angeboten)
        </label>
        <h3>Versionen</h3>
        <div id="f-versionen" class="versionen-liste"></div>
        <button id="f-version-neu" type="button" class="link">+ Version hinzufügen</button>
        <div class="aktionen">
          <button type="submit" class="knopf knopf--haupt">Speichern</button>
          <button id="f-abbrechen" type="button" class="knopf">Abbrechen</button>
        </div>
        <p id="f-meldung" class="meldung" role="status" aria-live="polite"></p>
      </form>
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

function ean13Pruefziffer(zwoelf) {
  let summe = 0;
  for (let i = 0; i < 12; i++) summe += Number(zwoelf[i]) * (i % 2 ? 3 : 1);
  return (10 - (summe % 10)) % 10;
}

// Kurze Rückmeldung zur GTIN beim Tippen. Maßgeblich ist die Prüfung im Server.
function gtinHinweis(gtin) {
  if (!gtin) return { ok: false, text: "" };
  if (!/^\d+$/.test(gtin)) return { ok: false, text: "nur Ziffern" };
  if (gtin.length === 12) return { ok: false, text: `12 Ziffern – Prüfziffer wäre ${ean13Pruefziffer(gtin)}` };
  if (gtin.length !== 13) return { ok: false, text: `${gtin.length} von 13 Ziffern` };
  const soll = ean13Pruefziffer(gtin);
  return Number(gtin[12]) === soll
    ? { ok: true, text: "✓ gültig" }
    : { ok: false, text: `Prüfziffer falsch (müsste ${soll} sein)` };
}

function el(tag, eigenschaften = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, w] of Object.entries(eigenschaften)) {
    if (k === "data") Object.assign(e.dataset, w);
    else if (k in e) e[k] = w;
    else e.setAttribute(k, w);
  }
  e.append(...kinder.filter((k) => k !== null && k !== undefined));
  return e;
}

class EtikettenApp extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = VORLAGE;
    this.zustand = {
      kaffees: [],          // aktive Kaffees (nur aktive Versionen) zum Drucken
      kaffee: null,         // gewählte Kaffee-ID
      version: null,        // gewählte Versions-ID
      mhdManuell: false,
      vorschauAktiv: true,
      vorschauNr: 0,        // verwirft veraltete Vorschau-Antworten
      vorschauUrl: null,
      vorschauSchluessel: "", // Kaffee + Version + MHD der angezeigten Vorschau
      alleKaffees: [],      // für die Verwaltung, inkl. archivierte
      bearbeitet: null,     // ID des Kaffees im Formular, "" = neuer Kaffee, null = keins
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
    this.kaffeesLaden(true);
  }

  disconnectedCallback() {
    clearTimeout(this.vorschauTimer);
  }

  $(id) {
    return this.shadowRoot.getElementById(id);
  }

  alle(selektor, wurzel = this.shadowRoot) {
    return [...wurzel.querySelectorAll(selektor)];
  }

  get apiBasis() {
    return (this.getAttribute("api") || "/api").replace(/\/+$/, "");
  }

  async api(pfad, daten, methode) {
    const optionen = daten === undefined ? {} : {
      method: methode || "POST",
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

  meldung(text, art = "", id = "meldung") {
    const e = this.$(id);
    e.textContent = text;
    e.className = "meldung" + (art ? ` meldung--${art}` : "");
  }

  // --- Ansichten --------------------------------------------------------------

  ansichtZeigen(name) {
    for (const b of this.alle("[data-ansicht]")) b.setAttribute("aria-pressed", String(b.dataset.ansicht === name));
    this.$("ansicht-drucken").hidden = name !== "drucken";
    this.$("ansicht-produkte").hidden = name !== "produkte";
    if (name === "produkte") this.verwaltungLaden();
  }

  // --- Status -----------------------------------------------------------------

  async statusLaden() {
    const knopf = this.$("status");
    knopf.className = "status status--laedt";
    this.$("status-text").textContent = "Prüfe Drucker …";
    try {
      const s = await this.api("/status");
      this.zustand.vorschauAktiv = s.vorschau;
      this.$("reiter").hidden = !s.produkte_bearbeiten;
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

  // --- Kaffee & Version wählen ------------------------------------------------

  kaffeeDaten() {
    return this.zustand.kaffees.find((k) => k.id === this.zustand.kaffee) || null;
  }

  versionDaten() {
    const k = this.kaffeeDaten();
    return k ? k.versionen.find((v) => v.id === this.zustand.version) || null : null;
  }

  async kaffeesLaden(start = false) {
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
      const v = k.versionen;
      const info = v.length === 1 ? `${v[0].gtin} · ${v[0].bezeichnung}` : `${v.length} Versionen`;
      const b = el("button", { type: "button", className: "kachel", role: "radio", data: { id: k.id } },
        el("strong", { textContent: k.anzeigename }),
        el("small", { textContent: `${info} · ${k.mhd_monate} Mon.` }));
      b.setAttribute("aria-checked", "false");
      b.addEventListener("click", () => this.kaffeeWaehlen(k.id));
      return b;
    }));
    const vorgabe = start ? this.getAttribute("kaffee") : this.zustand.kaffee;
    if (vorgabe && this.zustand.kaffees.some((k) => k.id === vorgabe)) {
      this.kaffeeWaehlen(vorgabe, start ? this.getAttribute("version") : this.zustand.version);
    } else {
      this.zustand.kaffee = null;
      this.zustand.version = null;
      this.versionenZeigen();
      this.aktualisieren();
    }
  }

  kaffeeWaehlen(id, versionWunsch = null) {
    const neu = id !== this.zustand.kaffee;
    this.zustand.kaffee = id;
    for (const k of this.alle(".kachel")) k.setAttribute("aria-checked", String(k.dataset.id === id));
    const versionen = this.kaffeeDaten().versionen;
    const wunsch = versionWunsch || (neu ? null : this.zustand.version);
    this.zustand.version = versionen.length === 1 ? versionen[0].id
      : versionen.some((v) => v.id === wunsch) ? wunsch : null;
    this.versionenZeigen();
    if (this.zustand.mhdManuell) {
      this.aktualisieren();
    } else {
      this.mhdBerechnen();
    }
  }

  versionenZeigen() {
    const k = this.kaffeeDaten();
    const feld = this.$("versionen-feld");
    feld.hidden = !k || k.versionen.length < 2;
    if (feld.hidden) return;
    this.$("versionen").replaceChildren(...k.versionen.map((v) => {
      const b = el("button", { type: "button", className: "chip", role: "radio", data: { id: v.id } },
        el("strong", { textContent: v.bezeichnung }), el("small", { textContent: v.gtin }));
      b.setAttribute("aria-checked", String(v.id === this.zustand.version));
      b.addEventListener("click", () => this.versionWaehlen(v.id));
      return b;
    }));
  }

  versionWaehlen(id) {
    this.zustand.version = id;
    for (const c of this.alle(".chip")) c.setAttribute("aria-checked", String(c.dataset.id === id));
    this.aktualisieren();
  }

  auftrag() {
    return { kaffee: this.zustand.kaffee, version: this.zustand.version, mhd: this.$("mhd").value, menge: this.menge() };
  }

  menge() {
    const n = parseInt(this.$("menge").value, 10);
    return Number.isFinite(n) ? Math.min(999, Math.max(1, n)) : 1;
  }

  // --- MHD --------------------------------------------------------------------

  async mhdBerechnen() {
    if (!this.zustand.kaffee) return;
    const abgepackt = this.$("abgepackt").value || heuteIso();
    try {
      const r = await this.api(`/mhd?kaffee=${encodeURIComponent(this.zustand.kaffee)}&abgepackt=${abgepackt}`);
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
    const k = this.kaffeeDaten();
    const v = this.versionDaten();
    const knopf = this.$("drucken");
    knopf.disabled = !v;
    if (!k) {
      knopf.textContent = "Drucken";
    } else if (!v) {
      knopf.textContent = "Version wählen";
    } else {
      const zusatz = k.versionen.length > 1 ? ` (${v.bezeichnung})` : "";
      knopf.textContent = `${this.menge()} × ${k.anzeigename}${zusatz} drucken`;
      if (this.$("mhd").value) {
        knopf.append(el("small", { textContent: `MHD: ${deutschesDatum(this.$("mhd").value)}` }));
      }
    }
    clearTimeout(this.vorschauTimer);
    this.vorschauTimer = setTimeout(() => this.vorschauLaden(), 250);
    if (!this.$("zpl").hidden) this.zplZeigen();
  }

  async vorschauLaden() {
    const z = this.zustand;
    const bild = this.$("vorschau-bild");
    const text = this.$("vorschau-text");
    if (!z.kaffee || !z.version || !this.$("mhd").value) {
      bild.hidden = true;
      z.vorschauSchluessel = "";
      text.textContent = z.kaffee ? "Version wählen für eine Vorschau" : "Kaffee wählen für eine Vorschau";
      return;
    }
    if (!z.vorschauAktiv) {
      text.textContent = "Vorschau ist ausgeschaltet (config.toml).";
      return;
    }
    const schluessel = `${z.kaffee}|${z.version}|${this.$("mhd").value}`;
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
    if (!this.versionDaten() || knopf.classList.contains("laeuft")) return;
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
    if (!this.versionDaten()) {
      pre.textContent = "Erst Kaffee und Version wählen.";
      return;
    }
    try {
      pre.textContent = (await this.api("/zpl", this.auftrag())).zpl;
    } catch (e) {
      pre.textContent = e.message;
    }
  }

  // --- Produkte verwalten -----------------------------------------------------

  async verwaltungLaden() {
    const fehler = this.$("liste-fehler");
    try {
      this.zustand.alleKaffees = await this.api("/produkte?alle=1");
      fehler.hidden = true;
    } catch (e) {
      fehler.hidden = false;
      fehler.textContent = e.message;
      return;
    }
    this.listeZeigen();
  }

  listeZeigen() {
    const mitArchiv = this.$("archiv-zeigen").checked;
    const liste = this.zustand.alleKaffees.filter((k) => mitArchiv || !k.archiviert);
    this.$("kaffee-liste").replaceChildren(...liste.map((k) => {
      const aktiv = k.versionen.filter((v) => !v.archiviert);
      const info = aktiv.map((v) => v.bezeichnung).join(", ") || "keine aktive Version";
      const b = el("button", { type: "button", data: { id: k.id } },
        el("strong", { textContent: k.anzeigename }),
        k.archiviert ? el("span", { className: "marke", textContent: "archiviert" }) : null,
        el("small", { textContent: `${info} · ${k.mhd_monate} Mon.` }));
      b.setAttribute("aria-current", String(k.id === this.zustand.bearbeitet));
      b.addEventListener("click", () => this.formularOeffnen(k));
      return el("li", {}, b);
    }));
  }

  formularOeffnen(kaffee) {
    this.zustand.bearbeitet = kaffee ? kaffee.id : "";
    this.$("formular-leer").hidden = true;
    this.$("formular").hidden = false;
    this.$("formular-titel").textContent = kaffee ? kaffee.anzeigename : "Neuer Kaffee";
    this.$("f-name").value = kaffee ? kaffee.name : "";
    this.$("f-monate").value = kaffee ? kaffee.mhd_monate : 12;
    this.$("f-archiv-zeile").hidden = !kaffee;
    this.$("f-archiviert").checked = Boolean(kaffee && kaffee.archiviert);
    const versionen = kaffee ? kaffee.versionen : [null];
    this.$("f-versionen").replaceChildren(...versionen.map((v) => this.versionZeile(v)));
    this.meldung("", "", "f-meldung");
    this.listeZeigen();
    this.$("f-name").focus();
  }

  formularSchliessen() {
    this.zustand.bearbeitet = null;
    this.$("formular").hidden = true;
    this.$("formular-leer").hidden = false;
    this.listeZeigen();
  }

  versionZeile(v) {
    const gtin = el("input", { className: "v-gtin", inputMode: "numeric", maxLength: 13, autocomplete: "off",
                                value: v ? v.gtin : "" });
    const pruefung = el("small", { className: "v-pruefung" });
    const pruefen = () => {
      const h = gtinHinweis(gtin.value.trim());
      pruefung.textContent = h.text;
      pruefung.className = "v-pruefung" + (h.text ? (h.ok ? " gut" : " schlecht") : "");
    };
    gtin.addEventListener("input", pruefen);
    pruefen();
    const layout = el("select", { className: "v-layout" }, el("option", { value: "standard", textContent: "Standard" }));
    layout.value = v ? v.layout : "standard";
    const zeile = el("div", { className: "version-zeile", data: { id: v ? v.id : "" } },
      el("label", {}, el("span", { textContent: "Bezeichnung" }),
        el("input", { className: "v-bezeichnung", placeholder: "z. B. Edeka", maxLength: 40, value: v ? v.bezeichnung : "" })),
      el("label", {}, el("span", { textContent: "GTIN / EAN-13" }), gtin, pruefung),
      el("label", {}, el("span", { textContent: "Layout" }), layout));
    if (v) {
      // Gespeicherte Versionen werden nicht gelöscht, nur archiviert (Druckprotokoll).
      zeile.append(el("label", { className: "haken" },
        el("input", { type: "checkbox", className: "v-archiviert", checked: v.archiviert }), "archiviert"));
    } else {
      const weg = el("button", { type: "button", className: "link", textContent: "entfernen" });
      weg.addEventListener("click", () => zeile.remove());
      zeile.append(weg);
    }
    return zeile;
  }

  async speichern(ereignis) {
    ereignis.preventDefault();
    const id = this.zustand.bearbeitet;
    const daten = {
      name: this.$("f-name").value.trim(),
      mhd_monate: Number(this.$("f-monate").value),
      archiviert: this.$("f-archiviert").checked,
      versionen: this.alle(".version-zeile", this.$("f-versionen")).map((z) => ({
        id: z.dataset.id || undefined,
        bezeichnung: z.querySelector(".v-bezeichnung").value.trim(),
        gtin: z.querySelector(".v-gtin").value.trim(),
        layout: z.querySelector(".v-layout").value,
        archiviert: Boolean(z.querySelector(".v-archiviert")?.checked),
      })),
    };
    this.meldung("Speichere …", "", "f-meldung");
    try {
      const r = id
        ? await this.api(`/kaffees/${encodeURIComponent(id)}`, daten, "PUT")
        : await this.api("/kaffees", daten);
      await this.verwaltungLaden();
      this.formularOeffnen(r.kaffee);
      this.meldung("Gespeichert.", "ok", "f-meldung");
      this.kaffeesLaden();
    } catch (e) {
      this.meldung(e.message, "fehler", "f-meldung");
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
    for (const b of this.alle("[data-ansicht]")) b.addEventListener("click", () => this.ansichtZeigen(b.dataset.ansicht));
    $("neu").addEventListener("click", () => this.formularOeffnen(null));
    $("archiv-zeigen").addEventListener("change", () => this.listeZeigen());
    $("f-version-neu").addEventListener("click", () => {
      const zeile = this.versionZeile(null);
      $("f-versionen").append(zeile);
      zeile.querySelector("input").focus();
    });
    $("f-abbrechen").addEventListener("click", () => this.formularSchliessen());
    $("formular").addEventListener("submit", (e) => this.speichern(e));
  }
}

if (!customElements.get("etiketten-app")) customElements.define("etiketten-app", EtikettenApp);
