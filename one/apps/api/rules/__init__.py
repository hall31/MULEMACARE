"""Module rules (lot L2) : produits versionnés et moteur de règles déterministe.

- ``engine.evaluate`` : fonction pure (faits + catalogue de versions -> décision), sans base,
  sans horloge, sans LLM ;
- ``repository.RulesRepository`` : chargement async des versions publiées (PostgreSQL) ;
- ``versions.select_in_force`` : version en vigueur à la date du soin (R3).
"""
