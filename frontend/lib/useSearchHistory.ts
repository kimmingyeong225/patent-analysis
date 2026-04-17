"use client";

import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "patentai_history";
const MAX = 5;

export function useSearchHistory() {
  const [history, setHistory] = useState<string[]>([]);

  // SSR 안전: localStorage는 클라이언트에서만
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setHistory(JSON.parse(raw));
    } catch {}
  }, []);

  const add = useCallback((query: string) => {
    setHistory((prev) => {
      const next = [query, ...prev.filter((q) => q !== query)].slice(0, MAX);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const remove = useCallback((query: string) => {
    setHistory((prev) => {
      const next = prev.filter((q) => q !== query);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setHistory([]);
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
  }, []);

  return { history, add, remove, clear };
}
