"use client";

import { useState, useRef, useEffect } from "react";

export interface LangOption {
  code: string;
  name: string;
  label: string;
}

// Flag emoji from country code (cs->CZ, en->GB, ja->JP, etc.)
export const FLAG: Record<string, string> = {
  cs: "\u{1F1E8}\u{1F1FF}", // CZ
  sk: "\u{1F1F8}\u{1F1F0}", // SK
  en: "\u{1F1EC}\u{1F1E7}", // GB
  de: "\u{1F1E9}\u{1F1EA}", // DE
  pl: "\u{1F1F5}\u{1F1F1}", // PL
  hu: "\u{1F1ED}\u{1F1FA}", // HU
  fr: "\u{1F1EB}\u{1F1F7}", // FR
  es: "\u{1F1EA}\u{1F1F8}", // ES
  it: "\u{1F1EE}\u{1F1F9}", // IT
  pt: "\u{1F1F5}\u{1F1F9}", // PT
  ru: "\u{1F1F7}\u{1F1FA}", // RU
  ja: "\u{1F1EF}\u{1F1F5}", // JP
  ko: "\u{1F1F0}\u{1F1F7}", // KR
  zh: "\u{1F1E8}\u{1F1F3}", // CN
  nl: "\u{1F1F3}\u{1F1F1}", // NL
  sv: "\u{1F1F8}\u{1F1EA}", // SE
  da: "\u{1F1E9}\u{1F1F0}", // DK
  no: "\u{1F1F3}\u{1F1F4}", // NO
  fi: "\u{1F1EB}\u{1F1EE}", // FI
  ro: "\u{1F1F7}\u{1F1F4}", // RO
  tr: "\u{1F1F9}\u{1F1F7}", // TR
  el: "\u{1F1EC}\u{1F1F7}", // GR
  uk: "\u{1F1FA}\u{1F1E6}", // UA
  hr: "\u{1F1ED}\u{1F1F7}", // HR
  bg: "\u{1F1E7}\u{1F1EC}", // BG
};

function flag(code: string): string {
  return FLAG[code] || "\u{1F3F3}\u{FE0F}";
}

interface Props {
  options: LangOption[];
  selected: string[];
  onChange: (codes: string[]) => void;
  /** Show "All" option at top */
  showAll?: boolean;
  /** Compact mode for search bar */
  compact?: boolean;
  /** Placeholder when nothing selected */
  placeholder?: string;
}

export default function LanguageSelect({
  options,
  selected,
  onChange,
  showAll = false,
  compact = false,
  placeholder = "Languages",
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const allSelected = selected.length === 0 || selected.length === options.length;

  function toggle(code: string) {
    if (selected.includes(code)) {
      const next = selected.filter((c) => c !== code);
      onChange(next.length === 0 ? [options[0]?.code || "cs"] : next);
    } else {
      onChange([...selected, code]);
    }
  }

  function selectAll() {
    onChange(options.map((o) => o.code));
  }

  // Build display text
  let displayText: string;
  if (allSelected && showAll) {
    displayText = "All";
  } else if (selected.length <= 3) {
    displayText = selected.map((c) => `${flag(c)} ${c.toUpperCase()}`).join("  ");
  } else {
    displayText = `${selected.slice(0, 2).map((c) => flag(c)).join(" ")} +${selected.length - 2}`;
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-100 text-sm hover:border-zinc-600 transition-colors ${
          compact ? "px-3 py-2.5" : "px-3 py-2 w-full"
        }`}
      >
        <span className="truncate">
          {selected.length === 0 ? placeholder : displayText}
        </span>
        <svg
          className={`w-4 h-4 text-zinc-500 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-64 max-h-72 overflow-y-auto rounded-lg bg-zinc-800 border border-zinc-700 shadow-xl">
          {showAll && (
            <button
              type="button"
              onClick={selectAll}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-zinc-700/50 transition-colors border-b border-zinc-700/50 ${
                allSelected ? "text-violet-400" : "text-zinc-400"
              }`}
            >
              <span className="w-5 h-5 rounded border flex items-center justify-center text-xs shrink-0 border-zinc-600">
                {allSelected && "\u2713"}
              </span>
              <span>All languages</span>
            </button>
          )}
          {options.map((lang) => {
            const checked = selected.includes(lang.code);
            return (
              <button
                key={lang.code}
                type="button"
                onClick={() => toggle(lang.code)}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-zinc-700/50 transition-colors text-left"
              >
                <span
                  className={`w-5 h-5 rounded border flex items-center justify-center text-xs shrink-0 transition-colors ${
                    checked
                      ? "bg-violet-600 border-violet-500 text-white"
                      : "border-zinc-600"
                  }`}
                >
                  {checked && "\u2713"}
                </span>
                <span className="text-base leading-none">{flag(lang.code)}</span>
                <span className="text-zinc-100 font-medium">{lang.label}</span>
                <span className="text-zinc-500">{lang.name}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
