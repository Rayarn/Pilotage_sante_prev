#!/usr/bin/env bash
# Regenere les presentations (PPTX + PDF) des arretes 2021 a 2025 a partir de la livraison locale.
set -euo pipefail
cd "$(dirname "$0")/../.."
python outils/reporting/preparer_deck.py "$@"
for n in ${@:-2021 2022 2023 2024 2025}; do
  NODE_PATH=$(npm root -g) node outils/reporting/generer_deck.js "$n"
  (cd "reporting/$n" && soffice --headless --convert-to pdf "Arrete_provisions_$n.pptx" >/dev/null 2>&1 || \
     python /mnt/skills/public/pptx/scripts/office/soffice.py --headless --convert-to pdf "Arrete_provisions_$n.pptx" >/dev/null 2>&1)
done
