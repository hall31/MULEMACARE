"use client";

import { useState } from "react";
import { t } from "@/i18n";
import { Button, ScreenTitle } from "../ui";
import { ScreenLayout } from "./ScreenLayout";

interface Props {
  displayName: string;
  busy: boolean;
  onValidate: (code: string) => void;
  onResend: () => void;
  onIncomplete: () => void;
}

export function CodeScreen({ displayName, busy, onValidate, onResend, onIncomplete }: Props) {
  const [code, setCode] = useState("");

  function submit() {
    if (!/^[0-9]{6}$/.test(code)) {
      onIncomplete();
      return;
    }
    onValidate(code);
  }

  return (
    <ScreenLayout
      footer={
        <>
          <Button onClick={submit} busy={busy} disabled={busy} trailing="arrow">
            {t("code.validate")}
          </Button>
          <Button variant="secondary" onClick={onResend} disabled={busy}>
            {t("code.resend")}
          </Button>
        </>
      }
    >
      <ScreenTitle>{t("code.title")}</ScreenTitle>
      <p>{t("code.explain", { name: displayName })}</p>
      <div className="field-group">
        <label htmlFor="sms-code" className="field-label">
          {t("code.label")}
        </label>
        <input
          id="sms-code"
          name="sms-code"
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
          }}
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={6}
          autoComplete="one-time-code"
          className="field field-code amount"
        />
      </div>
    </ScreenLayout>
  );
}
