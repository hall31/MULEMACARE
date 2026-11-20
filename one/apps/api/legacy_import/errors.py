"""Erreurs à code stable de l'import (refus d'un import entier) et motifs de rejet d'une ligne.

Un REFUS (``ImportRefusedError``, IMP-xx) arrête tout avant la moindre écriture. Un REJET
(``RowRejectedError``, REJ-xx) écarte UNE ligne de la source, avec son motif, dans le rapport.
Ni l'un ni l'autre ne porte de valeur de la source : codes, noms de champs et clés d'origine
seulement (une valeur peut être un nom, un téléphone, un montant de soin…).
"""

from __future__ import annotations

from typing import Final

IMPORT_REFUSALS: Final[dict[str, str]] = {
    "IMP-01": "Devise de la source non fournie : elle se déclare, elle ne se devine jamais.",
    "IMP-02": "Devise de la source différente de celle de l'organisation : aucune conversion.",
    "IMP-03": "Requête refusée : la source ne reçoit que des lectures (SELECT).",
    "IMP-04": "Compte de la source avec des droits d'écriture : lecture seule exigée.",
    "IMP-05": "Organisation cible introuvable ou invisible sous le rôle applicatif.",
    "IMP-06": "Correspondance invalide (champ inconnu, obligatoire absent ou colonne interdite).",
    "IMP-07": "Pilote MySQL absent : dépendance à valider (specs/DEPENDENCIES.md).",
    "IMP-08": "Source illisible (fichier, table ou colonne absente).",
    "IMP-09": "Échec pendant l'écriture : lot annulé, import marqué en échec, à rejouer.",
}

ROW_REJECTIONS: Final[dict[str, str]] = {
    "REJ-01": "Statut absent de la table de correspondance.",
    "REJ-02": "Montant invalide (illisible, négatif ou non entier en francs CFA).",
    "REJ-03": "Champ obligatoire vide.",
    "REJ-04": "Référence introuvable (formule, version, adhérent, prestataire).",
    "REJ-05": "Format invalide (date, code, nombre, liste d'ayants droit).",
    "REJ-06": "Valeur hors vocabulaire déclaré (lien, type, pays).",
    "REJ-07": "Devise de la ligne différente de la devise déclarée.",
    "REJ-08": "Clé d'origine en double dans la source.",
    "REJ-09": "Taux non exprimable en points de base entiers.",
    "REJ-10": "Conflit avec One (une personne a déjà un contrat, période déjà cotisée).",
    "REJ-11": "Plusieurs lignes pour la même personne ou le même mois : choix humain requis.",
}


class ImportRefusedError(Exception):
    """L'import entier est refusé, avant toute écriture. ``action`` dit quoi faire."""

    def __init__(self, code: str, action: str) -> None:
        if code not in IMPORT_REFUSALS:
            raise ValueError(code)
        super().__init__(f"{code} : {IMPORT_REFUSALS[code]}")
        self.code = code
        self.message = IMPORT_REFUSALS[code]
        self.action = action


class RowRejectedError(Exception):
    """Une ligne est écartée : motif stable et champ en cause (jamais sa valeur)."""

    def __init__(self, code: str, field: str) -> None:
        if code not in ROW_REJECTIONS:
            raise ValueError(code)
        super().__init__(f"{code} ({field})")
        self.code = code
        self.field = field
