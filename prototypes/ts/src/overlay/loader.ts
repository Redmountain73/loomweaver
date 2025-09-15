/*
 * Loomweaver Overlay Loader (SPEC-003)
 * - Loads core + domain overlays (JSON)
 * - Precedence: last-loaded-wins (core first)
 * - Tracks conflicts for warnings
 * - Exposes a verb table for validator/compiler
 * - Compile-time expansion only
 */

/// <reference types="node" />

import * as fs from "fs";
import * as path from "path";

export type CoreVerb = "Make" | "Show" | "Return" | "Ask" | "Choose" | "Repeat" | "Call";

export interface VerbStep {
  to: CoreVerb;
  op?: string;
  sink?: string;
  kind?: string;
  defaultInto?: string;
  capability?: string; // e.g., network:fetch, audio:tts, image:gen
}

export interface VerbMapping {
  // simple mapping
  to?: CoreVerb;
  op?: string;
  sink?: string;
  kind?: string;
  defaultInto?: string;
  capability?: string;
  // composed mapping
  compose?: VerbStep[];
}

export interface Overlay {
  overlayVersion: string;
  domain: string; // e.g., "core", "research-writing-media"
  verbs: Record<string, VerbMapping>; // AuthorVerb -> Mapping
}

function isOverlay(x: unknown): x is Overlay {
  if (!x || typeof x !== "object") return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o["overlayVersion"] === "string" &&
    typeof o["domain"] === "string" &&
    typeof o["verbs"] === "object" && o["verbs"] !== null
  );
}

export interface VerbProvider {
  domain: string;
  version: string;
  mapping: VerbMapping;
}

export type VerbTable = Map<string, VerbProvider>;

export interface OverlayLoadOptions {
  /** resolve relative paths from this cwd (usually repo root) */
  cwd?: string;
}

export class OverlayRegistry {
  private overlays: Overlay[] = [];
  private table: VerbTable = new Map();
  private conflicts: Map<string, Set<string>> = new Map();

  static load(corePath: string, overlayPaths: string[] = [], opts: OverlayLoadOptions = {}): OverlayRegistry {
    const reg = new OverlayRegistry();
    const cwd = opts.cwd ?? process.cwd();

    const loadJson = (p: string): Overlay => {
      const abs = path.isAbsolute(p) ? p : path.join(cwd, p);
      const raw = fs.readFileSync(abs, "utf8");
      const json = JSON.parse(raw);
      if (!isOverlay(json)) throw new Error(`Overlay missing required fields: ${p}`);
      return json;
    };

    // Always load core first
    const core = loadJson(corePath);
    reg.overlays.push(core);

    // Then user overlays in order
    for (const p of overlayPaths) {
      reg.overlays.push(loadJson(p));
    }

    reg.buildVerbTable();
    return reg;
  }

  private buildVerbTable() {
    this.table.clear();
    this.conflicts.clear();

    for (const ov of this.overlays) {
      const domain = ov.domain;
      const version = ov.overlayVersion;
      for (const [verb, mapping] of Object.entries(ov.verbs)) {
        if (this.table.has(verb)) {
          if (!this.conflicts.has(verb)) this.conflicts.set(verb, new Set([this.table.get(verb)!.domain]));
          this.conflicts.get(verb)!.add(domain);
        }
        this.table.set(verb, { domain, version, mapping }); // last-loaded wins
      }
    }
  }

  /** Returns the effective provider for a given author verb, if any. */
  get(verb: string): VerbProvider | undefined {
    return this.table.get(verb);
  }

  /** List all conflicts as verb -> [domains...] (useful for validator warnings). */
  listConflicts(): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const [verb, set] of this.conflicts.entries()) out[verb] = Array.from(set);
    return out;
  }

  /** Dump the effective verb table (for --dump-effective-verbs). */
  dumpEffective(): Record<string, { domain: string; version: string; mapping: VerbMapping }> {
    const out: Record<string, { domain: string; version: string; mapping: VerbMapping }> = {};
    for (const [verb, prov] of this.table.entries()) out[verb] = prov;
    return out;
  }

  /** Expand a mapping to canonical steps (validator/compiler can call this). */
  static expand(mapping: VerbMapping): VerbStep[] {
    if (mapping.compose && mapping.compose.length > 0) return mapping.compose;
    if (mapping.to) {
      const { to, op, sink, kind, defaultInto, capability } = mapping;
      return [{ to, op, sink, kind, defaultInto, capability } as VerbStep];
    }
    throw new Error("Invalid mapping: must have `to` or `compose`");
  }
}

// Convenience resolver for CLI: --overlay <name> → agents/loomweaver/overlays/verbs.<name>.json
export function resolveOverlayPaths(names: string[], cwd = process.cwd()): string[] {
  return names.map((n) => path.join(cwd, "agents/loomweaver/overlays", `verbs.${n}.json`));
}

export default OverlayRegistry;
