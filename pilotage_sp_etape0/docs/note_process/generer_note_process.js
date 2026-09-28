// Note de process de l'arrete annuel (DOCX). Usage : node docs/note_process/generer_note_process.js
const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  BorderStyle, AlignmentType, LevelFormat, Footer, PageNumber, PageBreak } = require("docx");

const VIOLET = "3B2A55", PRUNE = "6E5A8C", TEXTE = "3E4753", SABLE = "CFC7B6", LIN = "E7E1D4";
const CORPS = "IBM Plex Sans", TITRE = "Spectral";
const LARGEUR = 9638; // A4, marges de 2 cm

const p = (texte, o = {}) => new Paragraph({ spacing: { after: 120 }, ...o,
  children: [new TextRun({ text: texte, font: CORPS, size: 21, color: TEXTE, ...(o.run || {}) })] });
const puce = (texte) => new Paragraph({ numbering: { reference: "puces", level: 0 }, spacing: { after: 60 },
  children: [new TextRun({ text: texte, font: CORPS, size: 21, color: TEXTE })] });
const num = (texte, ref = "numeros") => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60 },
  children: [new TextRun({ text: texte, font: CORPS, size: 21, color: TEXTE })] });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });

function tableau(entetes, lignes, largeurs) {
  const bord = { style: BorderStyle.SINGLE, size: 4, color: SABLE };
  const bords = { top: bord, bottom: bord, left: bord, right: bord };
  const cellule = (t, i, entete) => new TableCell({
    width: { size: largeurs[i], type: WidthType.DXA }, borders: bords,
    shading: entete ? { fill: LIN, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text: t, font: CORPS, size: 18, color: entete ? VIOLET : TEXTE, bold: entete })] })],
  });
  return new Table({
    width: { size: LARGEUR, type: WidthType.DXA }, columnWidths: largeurs,
    rows: [new TableRow({ tableHeader: true, children: entetes.map((t, i) => cellule(t, i, true)) }),
      ...lignes.map((l) => new TableRow({ children: l.map((t, i) => cellule(t, i, false)) }))],
  });
}
const espace = () => new Paragraph({ spacing: { after: 60 }, children: [] });

const contenu = [
  new Paragraph({ spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: "DALVERNE · ACTUARIAT", font: CORPS, size: 18, bold: true, color: PRUNE, characterSpacing: 40 })] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Note de process", font: TITRE, size: 64, bold: true, color: VIOLET })] }),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Arrêté annuel des provisions santé et prévoyance", font: TITRE, size: 32, color: "14181F" })] }),
  p("Mutuelle Orsane (portefeuille et données fictifs) · version 1.0 · applicable à chaque arrêté à partir de l'exercice 2021"),
  p("Ce document décrit qui fait quoi, quand et avec quels contrôles. Il ne change pas d'une année sur l'autre : ce qui varie (hypothèses, faits marquants) est porté par la note technique de l'exercice et par la table des hypothèses.", { spacing: { before: 600 } }),
  new Paragraph({ children: [new PageBreak()] }),

  h1("1. Objet et périmètre"),
  p("Le process couvre la production des provisions techniques au 31 décembre : PSAP et frais de gestion en santé, provisions mathématiques d'incapacité et d'invalidité, rentes en attente, maintien de la garantie décès, capitaux décès, IBNR et frais de gestion en prévoyance. Il s'appuie sur une chaîne Databricks (job « arrêté annuel », dix tâches) et sur des hypothèses versionnées."),
  p("Principe directeur : le calcul est automatique, déterministe et rejouable ; la validation reste humaine. Aucune provision ne peut être modifiée à la main dans les tables : une correction passe par la donnée source, une règle qualité ou une hypothèse, puis un rejeu."),

  h1("2. Calendrier"),
  tableau(["Échéance", "Étape", "Responsable", "Livrable"], [
    ["J-30", "Revue des hypothèses : série TME, barème de retraite, S/P a priori, méthodes", "Actuaire inventaire", "Ligne N de ref.hypotheses_arrete, projet de note technique"],
    ["J-15", "Validation des hypothèses par l'actuaire valideur", "Actuaire valideur", "Hypothèses figées (version NT-N.1)"],
    ["J (31/12)", "Date d'arrêté", "", ""],
    ["J+8", "Dépôt des extractions et du fichier témoin en zone d'atterrissage", "Gestion", "7 fichiers + _TEMOIN_N"],
    ["J+9", "Exécution du job arrêté annuel (tâches 00 à 09)", "Actuaire inventaire", "Tables gold, livraison, journal"],
    ["J+10 à J+12", "Analyse des écarts, levée des réserves, commentaires", "Actuaire inventaire", "Présentation d'arrêté, notes d'écart"],
    ["J+13", "Revue quatre yeux et validation au journal d'arrêté", "Actuaire valideur", "Journal : validation_actuaire = VALIDE"],
    ["J+15", "Transmission à la direction financière", "Actuaire inventaire", "Synthèse XLSX, manifeste"],
    ["J+20", "Comité des risques", "Directeur technique", "Présentation PPTX et PDF"],
    ["J+30", "Archivage et retour d'expérience", "Actuaire inventaire", "Dossier d'arrêté archivé"],
  ], [1300, 4038, 1900, 2400]),

  h1("3. Rôles et responsabilités"),
  tableau(["Activité", "Gestion", "Actuaire inventaire", "Actuaire valideur", "Data engineer", "Direction financière"], [
    ["Extractions et témoin", "R", "C", "", "C", "I"],
    ["Hypothèses de l'arrêté", "", "R", "A", "", "I"],
    ["Exploitation du job", "", "R", "", "C", ""],
    ["Maintenance de la plateforme et du code", "", "C", "I", "R", ""],
    ["Analyse des écarts et commentaires", "", "R", "A", "", "C"],
    ["Réconciliation comptable", "C", "R", "", "", "A"],
    ["Validation de l'arrêté", "", "R", "A", "", "I"],
  ], [2638, 1200, 1500, 1500, 1400, 1400]),
  p("R : réalise ; A : approuve ; C : consulté ; I : informé.", { spacing: { before: 80 } }),

  h1("4. Déroulement de la chaîne"),
  p("Chaque tâche lit les sorties de la précédente et écrit une partition d'exercice. En cas d'échec, la tâche fautive est relancée seule après correction : les tâches amont ne sont pas rejouées."),
  tableau(["Tâche", "Rôle", "Contrôle", "Si échec"], [
    ["00 Initialisation", "Schémas, référentiels, hypothèses de l'exercice", "Hypothèses présentes et conformes (taux sous le plafond recalculé)", "Bloquant : compléter la table d'hypothèses"],
    ["01 Disponibilité", "Comparaison des fichiers au témoin", "Présence, structure, lignes, somme de contrôle, sha256", "Bloquant : relivraison par la gestion"],
    ["02 Bronze", "Lecture typée, colonnes techniques", "Contrats d'interface", "Rejeu après correction du fichier"],
    ["03 Qualité", "22 règles du catalogue", "Seuils par règle", "Bloquant si règle bloquante ; validation si majeure"],
    ["04 Silver", "Rejets, quarantaines, corrections, enrichissement", "Réconciliation comptable (0,10 %)", "Bloquant : analyse avec la direction financière"],
    ["05 Triangles", "Agrégats d'entrée des moteurs", "", ""],
    ["06 Santé", "PSAP, Mack, jeux N et N-1", "", ""],
    ["07 Prévoyance", "PM, IBNR, PMGD, jeux N, N-1 et N-1 taux N", "", ""],
    ["08 Agrégation", "Synthèse, pont, charge par survenance, indicateurs", "", ""],
    ["09 Livraison", "Contrôles de cohérence, exports, journal", "Bouclage, signes, plafond, variations", "Bloquant ou réserve selon le contrôle"],
  ], [1700, 2800, 2738, 2400]),

  h1("5. Contrôles et blocages"),
  h2("5.1 Trois niveaux"),
  puce("Bloquant : la chaîne s'arrête ; aucun chiffre n'est livré tant que la cause n'est pas traitée et la tâche rejouée."),
  puce("Majeur hors seuil : la chaîne continue, la livraison porte une réserve ; l'actuaire valideur doit la lever explicitement au journal d'arrêté."),
  puce("Mineur ou alerte : tracé dans ops.dq_resultats ou ops.controles_livraison, commenté dans la présentation si utile."),
  h2("5.2 Conduite à tenir"),
  num("Lire la table de contrôle concernée (ops.controle_disponibilite, ops.dq_resultats, ops.reconciliation, ops.controles_livraison)."),
  num("Qualifier la cause : donnée source, règle trop stricte, anomalie métier réelle."),
  num("Corriger à la source (relivraison) de préférence ; à défaut, faire évoluer une règle ou une correction par une modification de code revue et versionnée."),
  num("Rejouer à partir de la tâche fautive ; consigner la décision au journal d'arrêté."),

  h1("6. Gestion des hypothèses"),
  p("Toute hypothèse susceptible d'évoluer figure dans ref.hypotheses_arrete. Une modification suit un circuit unique :"),
  num("proposition argumentée par l'actuaire inventaire (donnée de marché, texte réglementaire, jugement d'expert) ;", "numeros2"),
  num("mesure d'impact grâce au double calcul N et N-1, qui chiffre l'effet des hypothèses sur le stock ;", "numeros2"),
  num("validation par l'actuaire valideur avant J-15 ;", "numeros2"),
  num("nouvelle version de la note technique (NT-N.1) et régénération de ses exemples chiffrés ;", "numeros2"),
  num("publication de la ligne d'hypothèses ; toute exécution ultérieure l'utilise automatiquement.", "numeros2"),
  p("Le plafond du taux d'actualisation n'est jamais saisi : il est recalculé depuis la série mensuelle des TME. Un taux au-dessus du plafond bloque l'arrêté dès la tâche 00."),

  h1("7. Validation quatre yeux"),
  p("L'actuaire valideur n'a pas produit les chiffres. Il vérifie au minimum :"),
  puce("la conformité des hypothèses à la version validée et au plafond réglementaire ;"),
  puce("les réserves du journal (règles majeures hors seuil, variations supérieures à 25 %) et leur justification ;"),
  puce("le pont N-1 vers N : liquidation par garantie, effet des hypothèses séparé entre taux et barème ;"),
  puce("un échantillon de dossiers de prévoyance recalculés à partir de la note technique ;"),
  puce("la cohérence entre présentation, synthèse XLSX et tables gold (même manifeste)."),
  p("La validation est enregistrée dans ops.journal_arrete (champ validation_actuaire)."),

  h1("8. Archivage et traçabilité"),
  puce("Les tables bronze, silver, gold et ops sont partitionnées par exercice et conservées ; l'historique Delta permet de retrouver chaque version."),
  puce("Le volume de livraison contient, par exercice, les exports CSV, la synthèse XLSX, le JSON de reporting et un manifeste des empreintes sha256."),
  puce("Le journal d'arrêté relie chaque livraison à la version du code et à la version des hypothèses."),
  puce("Un arrêté passé se rejoue à l'identique avec le job de rejeu historique ; les résultats de référence du dépôt servent de test de non-régression."),

  h1("9. Incidents et retour d'expérience"),
  p("Un incident est toute situation qui empêche la livraison à J+9 ou qui conduit à une réserve. Il fait l'objet d'une fiche : description, impact chiffré, décision, action corrective et échéance."),
  p("Exemple de référence : la bascule du système de gestion santé fin 2023 a retardé les paiements et réémis des décomptes en double. La règle de doublons fonctionnels les a rejetés avant calcul, le S/P a priori a été appliqué aux trois derniers mois de soins, et le mali résiduel de 2024 a été documenté au retour d'expérience."),

  h1("10. Évolutions prévues"),
  puce("Tableau de bord Databricks alimenté par gold.kpi_exercice, gold.charge_survenance et gold.pont_provisions."),
  puce("Agent d'analyse (RAG) lisant les tables gold, la note technique et le journal, pour préparer les commentaires d'écart : il ne calcule jamais une provision."),
  puce("Déclenchement automatique du job à l'arrivée du fichier témoin et génération des présentations à partir du JSON de reporting."),
];

const doc = new Document({
  creator: "Dalverne", title: "Note de process : arrêté annuel santé-prévoyance",
  styles: {
    default: { document: { run: { font: CORPS, size: 21, color: TEXTE } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: TITRE, size: 32, bold: true, color: VIOLET }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: TITRE, size: 26, bold: true, color: PRUNE }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "puces", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numeros2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numeros", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: "Dalverne · Note de process · ", font: CORPS, size: 16, color: "6E7783" }),
      new TextRun({ children: [PageNumber.CURRENT], font: CORPS, size: 16, color: "6E7783" })] })] }) },
    children: contenu,
  }],
});
const sortie = path.join(__dirname, "note_de_process.docx");
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(sortie, b); console.log(sortie); });
