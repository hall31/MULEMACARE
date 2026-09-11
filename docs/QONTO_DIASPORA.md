# Qonto diaspora — ops

## Usage

1. Adhérent choisit **Virement Qonto** sur `/adhesion`.
2. Système crée le client `PENDING_PAYMENT` (CSSA = libellé obligatoire).
3. Affichage IBAN (env) + montant + libellé CSSA.
4. Preuve via WhatsApp optionnelle.
5. Ops confirme dans Admin → Paiements.

## Env (IONOS)

```bash
QONTO_IBAN=FR76…
QONTO_BIC=QNTOFRP1XXX
QONTO_ACCOUNT_NAME=MulemaCare Health Group
QONTO_BANK_LABEL=Qonto
```

Ne jamais committer l’IBAN réel.
