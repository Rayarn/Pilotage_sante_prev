// Generateur des presentations d'arrete (charte Dalverne, gabarit B).
// Usage : node outils/reporting/generer_deck.js 2025  ->  reporting/2025/Arrete_provisions_2025.pptx
// Tailles de police uniques sur tout le deck : surtitre 9,5 ; titre 30 ; corps 14 ; titre de carte 20 ;
// grand chiffre 56 ; graphiques et tableaux 12 ; pied de page et source 9. Rien n'est jamais reduit.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const RACINE = path.resolve(__dirname, "..", "..");
const n = process.argv[2] || "2025";
const d = JSON.parse(fs.readFileSync(path.join(RACINE, "reporting", n, `deck_${n}.json`), "utf8"));

const C = { ivoire: "F4F1EA", nuit: "14181F", violet: "3B2A55", prune: "6E5A8C", lavande: "B7ABCB", brume: "E4DEEC",
  sable: "CFC7B6", lin: "E7E1D4", gris: "A8B0BB", ardoise: "2C333E", texte: "3E4753", pied: "6E7783", blanc: "FFFFFF" };
const T = { titre: "Spectral", corps: "IBM Plex Sans" };
const F = { surtitre: 9.5, titre: 30, corps: 14, carte: 20, chiffre: 56, graphe: 12, pied: 9 };
const G = { x: 0.85, w: 11.63, droite: 12.48 };
const SOURCE = `Source : chaîne pilotage_sp, livraison de l'arrêté ${n}, hypothèses ${d.version}. Données fictives.`;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = `Arrêté des provisions santé-prévoyance ${n}`;
pres.company = "Dalverne";
let page = 0;

// ------------------------------------------------------------------ briques
function fond(s, couleur) { s.background = { color: couleur }; }
function surtitre(s, texte, couleur = C.prune) {
  s.addText(texte.toUpperCase(), { x: G.x, y: 0.62, w: 9, h: 0.25, margin: 0, fontFace: T.corps, fontSize: F.surtitre,
    bold: true, color: couleur, charSpacing: 2 });
}
function titre(s, texte, couleur = C.nuit) {
  s.addText(texte, { x: G.x, y: 1.02, w: G.w, h: 1.15, margin: 0, fontFace: T.titre, fontSize: F.titre, bold: true,
    color: couleur, valign: "top", paraSpaceAfter: 0 });
}
function pied(s, sombre = false, source = true) {
  page += 1;
  s.addText(`Dalverne   ${String(page).padStart(2, "0")}`, { x: 9.48, y: 6.92, w: 3.0, h: 0.25, margin: 0, align: "right",
    fontFace: T.corps, fontSize: F.pied, color: sombre ? C.gris : C.pied });
  if (source) s.addText(SOURCE, { x: G.x, y: 6.9, w: 8.4, h: 0.25, margin: 0, fontFace: T.corps, fontSize: F.pied,
    color: sombre ? C.gris : C.pied });
}
function corps(s, texte, o) {
  s.addText(texte, Object.assign({ margin: 0, fontFace: T.corps, fontSize: F.corps, color: C.texte, valign: "top",
    paraSpaceAfter: 6 }, o));
}
function puces(s, items, o) {
  const runs = items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } }));
  s.addText(runs, Object.assign({ margin: 0, fontFace: T.corps, fontSize: F.corps, color: C.texte, valign: "top",
    paraSpaceAfter: 10 }, o));
}
function cercles(s) {
  for (const r of [1.3, 2.1, 2.9]) {
    s.addShape(pres.shapes.OVAL, { x: 10.6 - r, y: 3.75 - r, w: 2 * r, h: 2 * r, fill: { type: "none" },
      line: { color: C.ardoise, width: 1 } });
  }
}
function filet(s, x, y, w, couleur = C.prune) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: couleur, width: 1 } });
}
function carte(s, x, y, w, h, sombre, num, tit, txt) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: sombre ? C.violet : C.lin }, line: { type: "none" } });
  s.addText(num, { x: x + 0.3, y: y + 0.3, w: w - 0.6, h: 0.3, margin: 0, fontFace: T.corps, fontSize: F.corps, bold: true,
    color: sombre ? C.lavande : C.prune });
  s.addText(tit, { x: x + 0.3, y: y + 0.75, w: w - 0.6, h: 0.75, margin: 0, fontFace: T.titre, fontSize: F.carte, bold: true,
    color: sombre ? C.blanc : C.nuit, valign: "top" });
  corps(s, txt, { x: x + 0.3, y: y + 1.6, w: w - 0.6, h: h - 1.8, color: sombre ? C.brume : C.texte });
}
const nb = (v, dec = 1) => v.toFixed(dec).replace(".", ",").replace("-", "\u2212");

// ------------------------------------------------------------------ 1. couverture
{
  const s = pres.addSlide(); fond(s, C.nuit); cercles(s);
  s.addText("DALVERNE", { x: G.x, y: 0.62, w: 4, h: 0.25, margin: 0, fontFace: T.corps, fontSize: F.surtitre, bold: true,
    color: C.ivoire, charSpacing: 4 });
  filet(s, G.x, 2.95, 0.9);
  s.addText(`Arrêté des provisions santé-prévoyance au 31 décembre ${n}`, { x: G.x, y: 3.15, w: 7.6, h: 1.15, margin: 0,
    fontFace: T.titre, fontSize: F.titre, bold: true, color: C.ivoire, valign: "top" });
  corps(s, `${d.entite} · synthèse de l'arrêté, méthodes et points d'attention`, { x: G.x, y: 4.45, w: 7.6, h: 0.4, color: C.gris });
  s.addText(`Comité des risques · ${d.version} · données fictives`, { x: G.x, y: 6.6, w: 7, h: 0.25, margin: 0,
    fontFace: T.corps, fontSize: F.pied, color: C.gris });
  page += 1;
}

// ------------------------------------------------------------------ 2. message cle
{
  const s = pres.addSlide(); fond(s, C.ivoire);
  filet(s, G.x, 2.35, 0.9);
  s.addText([{ text: d.titre_cle + " ", options: { color: C.nuit } }, { text: d.sous_titre_cle, options: { color: C.violet } }],
    { x: G.x, y: 2.55, w: 10.2, h: 2.5, margin: 0, fontFace: T.titre, fontSize: F.titre, bold: true, valign: "top" });
  corps(s, `Arrêté au ${d.date_arrete}, calculé de bout en bout par la chaîne automatisée ; chiffres relus et commentés par l'actuariat.`,
    { x: G.x, y: 5.35, w: 8.5, h: 0.6 });
  pied(s, false, false);
}

// ------------------------------------------------------------------ 3. deroule
{
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Déroulé"); titre(s, "Quatre temps pour valider l'arrêté");
  const lignes = [["01", "Synthèse", "Chiffres clés, faits marquants et passage N-1 vers N"],
    ["02", "Santé", "Rapport sinistres à primes, PSAP, incertitude et liquidation"],
    ["03", "Prévoyance", "Stock de sinistres, effet des hypothèses et liquidation"],
    ["04", "Qualité et méthodes", "Contrôles de données, hypothèses et recommandations"]];
  lignes.forEach(([num, lib, desc], i) => {
    const y = 2.55 + i * 0.95;
    s.addText(num, { x: G.x, y, w: 0.8, h: 0.4, margin: 0, fontFace: T.titre, fontSize: F.carte, bold: true, color: C.prune });
    s.addText(lib, { x: 1.9, y: y + 0.05, w: 3.6, h: 0.35, margin: 0, fontFace: T.corps, fontSize: F.corps, bold: true, color: C.nuit });
    corps(s, desc, { x: 5.9, y: y + 0.05, w: 6.5, h: 0.35 });
    filet(s, G.x, y + 0.7, G.w, C.sable);
  });
  pied(s, false, false);
}

// ------------------------------------------------------------------ 4. chiffres cles
{
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Synthèse"); titre(s, "L'arrêté en quatre chiffres");
  d.chiffres.forEach((c, i) => {
    const x = G.x + (i % 2) * 5.9, y = 2.4 + Math.floor(i / 2) * 2.15;
    s.addText(c.valeur, { x, y, w: 5.6, h: 1.0, margin: 0, fontFace: T.titre, fontSize: F.chiffre, bold: true, color: C.violet });
    corps(s, c.libelle, { x, y: y + 1.1, w: 5.2, h: 0.6 });
  });
  pied(s);
}

// ------------------------------------------------------------------ 5. faits marquants
{
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Faits marquants"); titre(s, `Trois faits structurent l'exercice ${n}`);
  const w = (G.w - 0.5) / 3;
  d.faits.forEach(([tete, texte], i) => carte(s, G.x + i * (w + 0.25), 2.45, w, 3.9, i === 0, String(i + 1).padStart(2, "0"), tete, texte));
  pied(s);
}

// ------------------------------------------------------------------ 6. repartition
{
  const r = d.repartition;
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Répartition");
  titre(s, `La prévoyance porte ${r.centre} des provisions, les rentes d'invalidité en tête`);
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Provisions", labels: r.labels, values: r.valeurs }], {
    x: G.x, y: 2.35, w: 4.6, h: 4.2, holeSize: 68, chartColors: [C.violet, C.sable], showLegend: false,
    showValue: false, showPercent: false, dataBorder: { pt: 1, color: C.ivoire } });
  s.addText(r.centre, { x: G.x + 1.3, y: 4.05, w: 2.0, h: 0.6, margin: 0, align: "center", fontFace: T.titre, fontSize: F.carte,
    bold: true, color: C.violet });
  s.addText("prévoyance", { x: G.x + 1.3, y: 4.6, w: 2.0, h: 0.3, margin: 0, align: "center", fontFace: T.corps,
    fontSize: F.graphe, color: C.texte });
  s.addText("Principales provisions de prévoyance", { x: 6.3, y: 2.45, w: 6, h: 0.35, margin: 0, fontFace: T.corps,
    fontSize: F.corps, bold: true, color: C.nuit });
  r.types.forEach((t, i) => {
    const y = 3.0 + i * 0.62;
    corps(s, t.type, { x: 6.3, y, w: 3.8, h: 0.35 });
    s.addText(t.montant, { x: 10.2, y, w: 2.28, h: 0.35, margin: 0, align: "right", fontFace: T.corps, fontSize: F.corps,
      bold: true, color: C.violet });
    filet(s, 6.3, y + 0.47, 6.18, C.sable);
  });
  corps(s, `Santé : ${r.sante}, soit des provisions courtes, liquidées pour l'essentiel en moins d'un an.`,
    { x: 6.3, y: 5.65, w: 6.18, h: 0.7 });
  pied(s);
}

// ------------------------------------------------------------------ 7. pont
{
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Passage N-1 vers N");
  const o = d.pont[0].valeur, cl = d.pont[d.pont.length - 1].valeur;
  titre(s, `De ${nb(o)} à ${nb(cl)}\u00a0M€ hors frais de gestion : la nouvelle survenance compense les règlements`);
  const x0 = G.x, y0 = 2.55, hZone = 3.5, wZone = 7.4, largeur = wZone / d.pont.length;
  let cumul = 0; const barres = [];
  d.pont.forEach((p) => {
    if (p.nature === "total") { barres.push([0, p.valeur]); cumul = p.valeur; }
    else { barres.push([cumul, cumul + p.valeur]); cumul += p.valeur; }
  });
  const vmax = Math.max(...barres.map((b) => Math.max(b[0], b[1]))) * 1.08;
  const vmin = Math.min(0, ...barres.map((b) => Math.min(b[0], b[1])));
  const echelle = (v) => y0 + 0.35 + (hZone - 0.35) * (1 - (v - vmin) / (vmax - vmin));
  d.pont.forEach((p, i) => {
    const [a, b] = barres[i];
    const haut = echelle(Math.max(a, b)), bas = echelle(Math.min(a, b));
    const couleur = p.nature === "total" ? C.violet : (p.valeur >= 0 ? C.prune : C.sable);
    const x = x0 + i * largeur + 0.12;
    s.addShape(pres.shapes.RECTANGLE, { x, y: haut, w: largeur - 0.24, h: Math.max(bas - haut, 0.02), fill: { color: couleur },
      line: { type: "none" } });
    const lib = p.nature === "total" ? nb(p.valeur) : (p.valeur >= 0 ? "+" : "") + nb(p.valeur);
    s.addText(lib, { x: x - 0.1, y: haut - 0.32, w: largeur - 0.04, h: 0.28, margin: 0, align: "center", fontFace: T.corps,
      fontSize: F.graphe, bold: true, color: C.nuit });
    s.addText(p.libelle, { x: x - 0.1, y: y0 + hZone + 0.08, w: largeur - 0.04, h: 0.5, margin: 0, align: "center",
      fontFace: T.corps, fontSize: F.graphe, color: C.texte, valign: "top" });
  });
  filet(s, x0, y0 + hZone, wZone, C.sable);
  puces(s, d.pont_commentaire, { x: 8.75, y: 2.6, w: 3.73, h: 3.9 });
  pied(s);
}

// ------------------------------------------------------------------ separateurs
function section(num, lib) {
  const s = pres.addSlide(); fond(s, C.nuit); cercles(s);
  s.addText(num, { x: G.x, y: 2.9, w: 2, h: 0.9, margin: 0, fontFace: T.titre, fontSize: F.chiffre, bold: true, color: C.prune });
  filet(s, G.x, 3.95, 0.9);
  s.addText(lib, { x: G.x, y: 4.15, w: 7, h: 0.6, margin: 0, fontFace: T.titre, fontSize: F.titre, bold: true, color: C.ivoire });
  pied(s, true, false);
}

// ------------------------------------------------------------------ 8-10. sante
section("01", "Santé");
{
  const sa = d.sante;
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Santé · rapport sinistres à primes");
  const der = sa.annees.length - 1;
  titre(s, `Le S/P par année de soins se tient : ${nb(sa.sp_col[der] * 100, 0)}\u00a0% en collectif, ${nb(sa.sp_ind[der] * 100, 0)}\u00a0% en individuel`);
  s.addChart(pres.charts.BAR, [{ name: "Individuel", labels: sa.annees, values: sa.sp_ind }, { name: "Collectif", labels: sa.annees, values: sa.sp_col }], {
    x: G.x, y: 2.35, w: G.w, h: 3.95, barDir: "col", barGrouping: "clustered", barGapWidthPct: 70, chartColors: [C.sable, C.violet],
    showValue: true, dataLabelFormatCode: "0%", dataLabelFontSize: F.graphe, dataLabelFontFace: T.corps, dataLabelColor: C.texte,
    dataLabelPosition: "outEnd", catAxisLabelFontSize: F.graphe, catAxisLabelFontFace: T.corps, catAxisLabelColor: C.pied,
    catAxisLineShow: false, valAxisHidden: true, valAxisMinVal: 0, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "t", legendFontSize: F.graphe, legendFontFace: T.corps, legendColor: C.texte });
  corps(s, "Charge ultime estimée (payé + PSAP) rapportée aux cotisations acquises de l'année de soins. 2020 : effet confinement.",
    { x: G.x, y: 6.35, w: G.w, h: 0.4 });
  pied(s);
}
{
  const sa = d.sante;
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Santé · provisions");
  titre(s, `PSAP santé de ${sa.cartes[0].valeur} : une provision courte, mesurée et encadrée`);
  const w = (G.w - 0.5) / 3;
  sa.cartes.forEach((c, i) => {
    const x = G.x + i * (w + 0.25);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.4, w, h: 2.55, fill: { color: i === 0 ? C.violet : C.lin }, line: { type: "none" } });
    s.addText(c.titre, { x: x + 0.3, y: 2.65, w: w - 0.6, h: 0.3, margin: 0, fontFace: T.corps, fontSize: F.corps, bold: true,
      color: i === 0 ? C.lavande : C.prune });
    s.addText(c.valeur, { x: x + 0.3, y: 3.0, w: w - 0.6, h: 0.6, margin: 0, fontFace: T.titre, fontSize: F.carte, bold: true,
      color: i === 0 ? C.blanc : C.nuit });
    corps(s, c.texte, { x: x + 0.3, y: 3.7, w: w - 0.6, h: 1.1, color: i === 0 ? C.brume : C.texte });
  });
  s.addText("Méthodes de l'arrêté", { x: G.x, y: 5.2, w: 5, h: 0.3, margin: 0, fontFace: T.corps, fontSize: F.corps, bold: true, color: C.nuit });
  puces(s, sa.methodes, { x: G.x, y: 5.55, w: G.w, h: 1.2, paraSpaceAfter: 2 });
  pied(s);
}

// ------------------------------------------------------------------ 11-13. prevoyance
section("02", "Prévoyance");
{
  const p = d.prevoyance;
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Prévoyance · stock de provisions");
  titre(s, `Les provisions de prévoyance atteignent ${p.total}, portées par l'invalidité`);
  const totaux = p.annees.map((_, i) => p.series.reduce((a, se) => a + se.valeurs[i], 0));
  const der = totaux.length - 1;
  // histogramme trace en formes : etiquettes au-dessus de chaque barre, derniere barre en violet (charte)
  const zx = G.x, zy = 2.55, zw = 7.3, zh = 3.55, pas = zw / totaux.length, vmax = Math.max(...totaux) * 1.1;
  totaux.forEach((v, i) => {
    const h = zh * v / vmax, x = zx + i * pas + 0.15, y = zy + zh - h;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: pas - 0.3, h, fill: { color: i === der ? C.violet : C.sable }, line: { type: "none" } });
    s.addText(nb(v), { x: x - 0.1, y: y - 0.32, w: pas - 0.1, h: 0.28, margin: 0, align: "center", fontFace: T.corps,
      fontSize: F.graphe, bold: true, color: C.nuit });
    s.addText(p.annees[i], { x: x - 0.1, y: zy + zh + 0.08, w: pas - 0.1, h: 0.28, margin: 0, align: "center", fontFace: T.corps,
      fontSize: F.graphe, color: C.pied });
  });
  filet(s, zx, zy + zh, zw, C.sable);
  s.addText("En M€, frais de gestion inclus", { x: G.x, y: 6.5, w: 5, h: 0.3, margin: 0, fontFace: T.corps, fontSize: F.graphe, color: C.pied });
  s.addText(`Répartition ${n}`, { x: 8.55, y: 2.45, w: 3.9, h: 0.35, margin: 0, fontFace: T.corps, fontSize: F.corps, bold: true, color: C.nuit });
  p.series.forEach((se, i) => {
    const y = 3.0 + i * 0.62;
    corps(s, se.nom, { x: 8.55, y, w: 2.2, h: 0.35 });
    s.addText(`${nb(se.valeurs[der])}\u00a0M€`, { x: 10.6, y, w: 1.88, h: 0.35, margin: 0, align: "right", fontFace: T.corps,
      fontSize: F.corps, bold: true, color: C.violet });
    filet(s, 8.55, y + 0.47, 3.93, C.sable);
  });
  const e = p.encours;
  corps(s, `${e.INCAPACITE || 0} arrêts en cours, ${e.INVALIDITE || 0} rentes d'invalidité en service, ${e.DECES || 0} capitaux décès à régler.`,
    { x: 8.55, y: 5.0, w: 3.93, h: 1.2 });
  pied(s);
}
{
  const p = d.prevoyance;
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Prévoyance · hypothèses et liquidation");
  titre(s, "L'effet des hypothèses se lit séparément de l'aléa de liquidation");
  const colonnes = [
    ["Effet des hypothèses", [["Taux d'actualisation", p.effet_taux], ["Barème de retraite et autres", p.effet_autres]], true],
    ["Liquidation de l'arrêté N-1", p.liquidation.map((l) => [l.garantie, l.taux]), false],
    ["IBNR (survenances récentes)", Object.entries(p.ibnr), false]];
  const w = (G.w - 0.5) / 3;
  colonnes.forEach(([tit, lignes, sombre], i) => {
    const x = G.x + i * (w + 0.25);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.4, w, h: 3.6, fill: { color: sombre ? C.violet : C.lin }, line: { type: "none" } });
    s.addText(tit, { x: x + 0.3, y: 2.65, w: w - 0.6, h: 0.75, margin: 0, fontFace: T.titre, fontSize: F.carte, bold: true,
      color: sombre ? C.blanc : C.nuit, valign: "top" });
    lignes.forEach(([lib, val], j) => {
      const y = 3.6 + j * 0.62;
      corps(s, lib, { x: x + 0.3, y, w: w - 1.9, h: 0.5, color: sombre ? C.brume : C.texte });
      s.addText(val, { x: x + w - 1.6, y, w: 1.3, h: 0.35, margin: 0, align: "right", fontFace: T.corps, fontSize: F.corps,
        bold: true, color: sombre ? C.blanc : C.violet });
      filet(s, x + 0.3, y + 0.5, w - 0.6, sombre ? C.prune : C.sable);
    });
  });
  corps(s, "Liquidation : écart entre la provision N-1 et la somme des règlements N et de la provision résiduelle, positif = boni.",
    { x: G.x, y: 6.2, w: G.w, h: 0.5 });
  pied(s);
}

// ------------------------------------------------------------------ 14-16. qualite et methodes
section("03", "Qualité et méthodes");
{
  const q = d.qualite;
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Qualité des données");
  titre(s, q.nb_hors_seuil ? `${q.nb_hors_seuil} règle${q.nb_hors_seuil > 1 ? "s" : ""} hors seuil sur ${q.nb_regles}, traitée${q.nb_hors_seuil > 1 ? "s" : ""} avant calcul`
    : `Les ${q.nb_regles} règles de qualité sont dans leur seuil`);
  s.addText(`${q.nb_conformes + q.nb_toleres}/${q.nb_regles}`, { x: G.x, y: 2.35, w: 4.2, h: 1.0, margin: 0, fontFace: T.titre,
    fontSize: F.chiffre, bold: true, color: C.violet });
  corps(s, `règles conformes ou dans leur tolérance. Écart à la balance comptable après nettoyage : ${q.reconciliation_max} au plus (tolérance 0,10 %) ; avant nettoyage en santé : ${q.ecart_brut_sante}.`,
    { x: G.x, y: 3.45, w: 4.0, h: 2.2 });
  const lignes = [[{ text: "Règle", options: { bold: true } }, { text: "Anomalies", options: { bold: true, align: "right" } },
    { text: "Sévérité", options: { bold: true } }, { text: "Action", options: { bold: true } }]];
  (q.hors_seuil.length ? q.hors_seuil : [{ libelle: "Aucune règle hors seuil", nb: "", severite: "", action: "" }]).forEach((r) =>
    lignes.push([r.libelle, { text: String(r.nb), options: { align: "right" } }, r.severite, r.action]));
  s.addTable(lignes, { x: 5.35, y: 2.45, w: 7.13, colW: [3.43, 1.2, 1.2, 1.3], fontFace: T.corps, fontSize: F.graphe, color: C.texte,
    border: { type: "solid", pt: 0.75, color: C.sable }, fill: { color: C.ivoire }, rowH: 0.42, valign: "middle", margin: 0.06 });
  if (q.reserves.length) {
    s.addText("Réserves portées au journal d'arrêté", { x: 5.35, y: 4.75, w: 7.13, h: 0.3, margin: 0, fontFace: T.corps,
      fontSize: F.corps, bold: true, color: C.nuit });
    puces(s, q.reserves, { x: 5.35, y: 5.15, w: 7.13, h: 1.5, paraSpaceAfter: 4 });
  }
  pied(s);
}
{
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Hypothèses");
  titre(s, `Hypothèses de l'arrêté : ${d.hypotheses[0][1]} de taux, barème ${d.hypotheses[2][1]}`);
  const lignes = [[{ text: "Hypothèse", options: { bold: true } }, { text: `Arrêté ${n}`, options: { bold: true, align: "right" } },
    { text: `Arrêté ${n - 1}`, options: { bold: true, align: "right" } }]];
  d.hypotheses.forEach(([a, b, c]) => lignes.push([a, { text: b, options: { align: "right", bold: b !== c, color: b !== c ? C.violet : C.texte } },
    { text: c, options: { align: "right" } }]));
  s.addTable(lignes, { x: G.x, y: 2.4, w: G.w, colW: [6.63, 2.5, 2.5], fontFace: T.corps, fontSize: F.graphe, color: C.texte,
    border: { type: "solid", pt: 0.75, color: C.sable }, fill: { color: C.ivoire }, rowH: 0.42, valign: "middle", margin: 0.06 });
  corps(s, "En violet : hypothèses modifiées par rapport à l'arrêté précédent. Plafond recalculé sur la série officielle des TME.",
    { x: G.x, y: 6.3, w: G.w, h: 0.4 });
  pied(s);
}
{
  const s = pres.addSlide(); fond(s, C.ivoire); surtitre(s, "Recommandations");
  titre(s, "Trois décisions à prendre avant l'arrêté suivant");
  const w = (G.w - 0.5) / 3;
  d.recommandations.forEach(([t, txt], i) => carte(s, G.x + i * (w + 0.25), 2.45, w, 3.9, i === 0, String(i + 1).padStart(2, "0"), t, txt));
  pied(s);
}

// ------------------------------------------------------------------ cloture
{
  const s = pres.addSlide(); fond(s, C.nuit); cercles(s);
  filet(s, G.x, 2.95, 0.9);
  s.addText("Le calcul est déterministe et tracé. Le jugement reste celui de l'actuaire.", { x: G.x, y: 3.15, w: 7.6, h: 1.2,
    margin: 0, fontFace: T.titre, fontSize: F.titre, bold: true, color: C.ivoire, valign: "top" });
  corps(s, `Annexes disponibles : tables gold de l'arrêté ${n}, note technique ${d.version}, note de process, journal d'arrêté.`,
    { x: G.x, y: 4.55, w: 7.6, h: 0.7, color: C.gris });
  pied(s, true, false);
}

const sortie = path.join(RACINE, "reporting", n, `Arrete_provisions_${n}.pptx`);
pres.writeFile({ fileName: sortie }).then(() => console.log(sortie));
