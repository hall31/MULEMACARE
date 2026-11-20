"""Module integrations (lot L9, R9) : HealthOS et résidence des données.

* ``egress`` : liste blanche ``infra/egress-allowlist.txt`` et garde réseau ``egress_guard``.
* ``transport`` : transport HTTP qui refuse tout hôte hors liste avant connexion.
* ``healthos`` : client FHIR minimal (identité, consultation, motif audité à la demande).
* ``healthos_sim`` : serveur HealthOS simulé pour les tests (L9, L5).
* ``deployment`` : configuration par pays ``infra/deploy/<pays>.toml``.
"""
