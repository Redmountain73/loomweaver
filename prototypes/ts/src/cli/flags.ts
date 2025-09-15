/*
 * Minimal CLI flag parser for SPEC-003
 * Supports:
 *   --overlay <name>              (repeatable)
 *   --no-unknown-verbs            (bool)
 *   --enforce-capabilities        (bool)
 *   --granted <capability>        (repeatable)
 *   --dump-effective-verbs        (bool)
 *   --ast <path>                  (author AST JSON file)
 */

export interface CliFlags {
  overlays: string[];            // e.g., ["research-writing-media"]
  noUnknownVerbs: boolean;
  enforceCapabilities: boolean;
  granted: string[];             // e.g., ["network:fetch"]
  dumpEffective: boolean;
  astPath?: string;              // path to author AST JSON
}

export function parseFlags(argv: string[] = process.argv.slice(2)): CliFlags {
  const flags: CliFlags = {
    overlays: [],
    noUnknownVerbs: false,
    enforceCapabilities: false,
    granted: [],
    dumpEffective: false,
    astPath: undefined,
  };

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case "--overlay":
        if (!argv[i + 1]) throw new Error("--overlay requires a name");
        flags.overlays.push(argv[++i]);
        break;
      case "--no-unknown-verbs":
        flags.noUnknownVerbs = true;
        break;
      case "--enforce-capabilities":
        flags.enforceCapabilities = true;
        break;
      case "--granted":
        if (!argv[i + 1]) throw new Error("--granted requires a capability name");
        flags.granted.push(argv[++i]);
        break;
      case "--dump-effective-verbs":
        flags.dumpEffective = true;
        break;
      case "--ast":
        if (!argv[i + 1]) throw new Error("--ast requires a file path");
        flags.astPath = argv[++i];
        break;
      default:
        if (a.startsWith("--")) throw new Error(`Unknown flag: ${a}`);
    }
  }

  return flags;
}

export default parseFlags;
