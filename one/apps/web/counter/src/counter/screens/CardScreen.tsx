"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { t } from "@/i18n";
import { Button, Icon, Notice, ScreenTitle } from "../ui";
import { ScreenLayout } from "./ScreenLayout";

const MEMBER_NUMBER = /^MC-[0-9]{8}$/;

interface DetectedBarcode {
  rawValue: string;
}
interface BarcodeDetectorLike {
  detect(source: HTMLVideoElement): Promise<DetectedBarcode[]>;
}
type BarcodeDetectorCtor = new (options: { formats: string[] }) => BarcodeDetectorLike;

function barcodeDetector(): BarcodeDetectorCtor | null {
  const candidate = (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector;
  return candidate ?? null;
}

interface Props {
  busy: boolean;
  onLookup: (memberNumber: string) => void;
  onScanned: (qrPayload: string) => void;
  /** Sous le formulaire : réglages de l'appareil (interrupteur de la mesure d'usage). */
  extra?: ReactNode;
}

export function CardScreen({ busy, onLookup, onScanned, extra }: Props) {
  const [number, setNumber] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanIssue, setScanIssue] = useState<"unsupported" | "denied" | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  function stopScan() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setScanning(false);
  }

  useEffect(() => stopScan, []);

  useEffect(() => {
    if (!scanning) return;
    const Detector = barcodeDetector();
    const video = videoRef.current;
    if (!Detector || !video) return;
    const detector = new Detector({ formats: ["qr_code"] });
    let active = true;
    const timer = window.setInterval(() => {
      if (!active || video.readyState < 2) return;
      detector
        .detect(video)
        .then((codes) => {
          const payload = codes[0]?.rawValue;
          if (active && payload) {
            active = false;
            stopScan();
            onScanned(payload);
          }
        })
        .catch(() => undefined);
    }, 300);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [scanning, onScanned]);

  async function startScan() {
    setScanIssue(null);
    if (!barcodeDetector() || !navigator.mediaDevices?.getUserMedia) {
      setScanIssue("unsupported");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      streamRef.current = stream;
      setScanning(true);
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play();
        }
      });
    } catch {
      setScanIssue("denied");
    }
  }

  function lookup() {
    const value = number.trim().toUpperCase();
    if (!MEMBER_NUMBER.test(value)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onLookup(value);
  }

  return (
    <ScreenLayout
      footer={
        <>
          {scanning ? (
            <Button variant="secondary" onClick={stopScan}>
              {t("card.stopScan")}
            </Button>
          ) : (
            <Button onClick={() => void startScan()} disabled={busy} trailing="qr">
              {t("card.scan")}
            </Button>
          )}
          <Button variant="secondary" onClick={lookup} busy={busy} disabled={busy}>
            {t("card.lookup")}
          </Button>
        </>
      }
    >
      <ScreenTitle>{t("card.title")}</ScreenTitle>
      <div className="scan">
        {scanning ? <video ref={videoRef} muted playsInline className="size-full object-cover" aria-label={t("card.scanning")} /> : <Icon name="qr" />}
      </div>
      {scanning ? <p className="text-center font-semibold">{t("card.scanning")}</p> : null}
      {scanIssue ? (
        <Notice tone="warn" role="alert">
          {t(scanIssue === "unsupported" ? "card.scanUnsupported" : "card.cameraDenied")}
        </Notice>
      ) : null}
      <div className="field-group">
        <label htmlFor="member-number" className="field-label">
          {t("card.numberLabel")}
        </label>
        <input
          id="member-number"
          name="member-number"
          value={number}
          onChange={(event) => setNumber(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") lookup();
          }}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          inputMode="text"
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? "member-number-error" : undefined}
          className="field id"
        />
        {invalid ? (
          <p id="member-number-error" className="field-error">
            <Icon name="alert" />
            <span>{t("card.numberInvalid")}</span>
          </p>
        ) : null}
      </div>
      {extra}
    </ScreenLayout>
  );
}
