"use client";

import { createElement, useEffect, useState, type ComponentType } from "react";

/**
 * Écrans secondaires chargés à part, hors du JavaScript initial de la carte (PERFORMANCE.md) :
 * bandeau de consentement, invitation à la découverte, compteur de la cloche, présentation au
 * comptoir. Contrairement à `React.lazy`, un chargement impossible (réseau coupé avant l'arrivée du
 * morceau) ne lève jamais : rien n'est affiché, et un nouvel essai part au retour du réseau. Rien
 * au rendu serveur ni à l'hydratation (pas d'écart entre le HTML et le premier rendu).
 */
export interface DeferredLoader<T> {
  get(): Promise<T>;
  peek(): T | null;
  preload(): void;
}

export function createDeferredLoader<T>(load: () => Promise<T>): DeferredLoader<T> {
  let loaded: T | null = null;
  let pending: Promise<T> | null = null;
  const get = (): Promise<T> => {
    if (loaded !== null) return Promise.resolve(loaded);
    pending ??= load().then(
      (value) => {
        loaded = value;
        return value;
      },
      (error: unknown) => {
        // L'échec n'est pas gardé : le prochain essai recharge.
        pending = null;
        throw error;
      },
    );
    return pending;
  };
  return { get, peek: () => loaded, preload: () => void get().catch(() => undefined) };
}

export type DeferredComponent<P> = ComponentType<P> & { preload(): void };

export function deferred<P extends object>(load: () => Promise<ComponentType<P>>): DeferredComponent<P> {
  const loader = createDeferredLoader(load);

  function Deferred(props: P) {
    const [Loaded, setLoaded] = useState<ComponentType<P> | null>(null);
    useEffect(() => {
      let alive = true;
      const attempt = () => {
        loader
          .get()
          .then((component) => {
            if (alive) setLoaded(() => component);
          })
          .catch(() => undefined);
      };
      attempt();
      window.addEventListener("online", attempt);
      return () => {
        alive = false;
        window.removeEventListener("online", attempt);
      };
    }, []);
    return Loaded ? createElement(Loaded, props) : null;
  }

  return Object.assign(Deferred, { preload: loader.preload });
}
