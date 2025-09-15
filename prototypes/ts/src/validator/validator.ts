/*
 * Loomweaver Validator + Overlay Expander (SPEC-003)
 * - Looks up author verbs in overlays
 * - Expands to canonical IR at compile time
 * - Warns on unknown verbs; optional error via --no-unknown-verbs
 * - Checks capabilities (warn by default; block via --enforce-capabilities)
 * - Stamps receipts with rawVerb + overlay info for auditability
 */

/// <reference types="node" />

import OverlayRegistry, { CoreVerb, VerbStep } from "../overlay/loader";

// --- Input AST (author view) ---
export interface AuthorNode {
  verb: string;                       // e.g., "Report"
  args?: Record<string, unknown>;     // free-form; passed through to steps
  loc?: { line: number; col: number };// optional source location
}

// --- Canonical IR (executor view) ---
export interface CanonicalInstr {
  to: CoreVerb;                        // Make | Show | Call | ...
  op?: string;
  sink?: string;
  kind?: string;
  defaultInto?: string;
  args?: Record<string, unknown>;      // merged author args
  valueVar?: string;                   // temp var carrying value between composed steps
}

// --- Receipts (audit trail) ---
export interface Receipt {
  rawVerb: string;                     // what author wrote
  mappedVerb: string;                  // e.g., "Make+Show" or "Call"
  overlayDomain: string;               // e.g., "core"
  overlayVersion: string;              // e.g., "0.1"
  capabilityCheck: {
    mode: "warn" | "block";
    capability?: string;               // e.g., network:fetch
    allowed: boolean;                  // true if granted or none required
    reason?: string;                   // present when blocked/warned
  };
  details: {
    stepIndex: number;                 // 0..n-1 in composed verb
    to: CoreVerb;
    op?: string;
    sink?: string;
    kind?: string;
    defaultInto?: string;
    args?: Record<string, unknown>;
    loc?: { line: number; col: number } | undefined;
  };
}

export interface ValidateFlags {
  noUnknownVerbs?: boolean;            // escalate unknown verbs to error
  enforceCapabilities?: boolean;       // block when required capability missing
  grantedCapabilities?: string[];      // capabilities available in this run
}

export interface ValidateResult {
  ir: CanonicalInstr[];
  receipts: Receipt[];
  warnings: string[];
  errors: string[];
}

function mappedVerbLabel(steps: VerbStep[]): string {
  return steps.map(s => s.to).join("+");
}

let tmpCounter = 0;
function nextTmp(): string { return `_tmp${tmpCounter++}`; }

function needsValue(step: VerbStep): boolean {
  // Heuristic: Show needs a value; Call/Make/Choose/etc. produce/consume depending on op.
  return step.to === "Show";
}

function producesValue(step: VerbStep): boolean {
  // For SPEC-003 MVP, assume Make and Call produce a value; others don't.
  return step.to === "Make" || step.to === "Call";
}

export function validateAndExpand(
  ast: AuthorNode[],
  registry: OverlayRegistry,
  flags: ValidateFlags = {}
): ValidateResult {
  const ir: CanonicalInstr[] = [];
  const receipts: Receipt[] = [];
  const warnings: string[] = [];
  const errors: string[] = [];

  const granted = new Set(flags.grantedCapabilities ?? []);
  const mode: "warn" | "block" = flags.enforceCapabilities ? "block" : "warn";

  for (const node of ast) {
    const rawVerb = node.verb;
    const provider = registry.get(rawVerb);

    if (!provider) {
      const msg = `Unknown verb: ${rawVerb}${node.loc ? ` at ${node.loc.line}:${node.loc.col}` : ""}`;
      if (flags.noUnknownVerbs) errors.push(msg); else warnings.push(msg);
      // pass-through as no-op to keep compilation moving (optional)
      continue;
    }

    const steps = OverlayRegistry.expand(provider.mapping);
    const mappedLabel = mappedVerbLabel(steps);

    // Compose chain value threading
    let lastVar: string | undefined;

    steps.forEach((step, idx) => {
      // Merge author args; step-specific fields take precedence on key collisions
      const mergedArgs: Record<string, unknown> = { ...(node.args ?? {}) };

      // If Show and no explicit value, thread previous tmp var
      if (needsValue(step) && lastVar && mergedArgs["value"] === undefined) {
        mergedArgs["value"] = { var: lastVar };
      }

      // Capability check (if overlay step declares one)
      const capability = step.capability; // may be undefined
      let allowed = true;
      let reason: string | undefined;
      if (capability && !granted.has(capability)) {
        allowed = false;
        reason = `Capability '${capability}' not granted`;
        if (mode === "warn") {
          warnings.push(`${rawVerb}[${idx}] requires ${capability} — continuing in warn mode`);
          allowed = true; // warn mode allows
        } else {
          errors.push(`${rawVerb}[${idx}] requires ${capability} — blocked by --enforce-capabilities`);
        }
      }

      const instr: CanonicalInstr = {
        to: step.to,
        op: step.op,
        sink: step.sink,
        kind: step.kind,
        defaultInto: step.defaultInto,
        args: mergedArgs,
      };

      // If this step produces a value, allocate a tmp var name to represent it
      if (producesValue(step)) {
        const t = nextTmp();
        instr.valueVar = t;
        lastVar = t;
      }

      ir.push(instr);

      // Receipt per step
      receipts.push({
        rawVerb,
        mappedVerb: mappedLabel,
        overlayDomain: provider.domain,
        overlayVersion: provider.version,
        capabilityCheck: { mode, capability, allowed, reason },
        details: {
          stepIndex: idx,
          to: step.to,
          op: step.op,
          sink: step.sink,
          kind: step.kind,
          defaultInto: step.defaultInto,
          args: mergedArgs,
          loc: node.loc,
        },
      });
    });
  }

  return { ir, receipts, warnings, errors };
}

export default validateAndExpand;
