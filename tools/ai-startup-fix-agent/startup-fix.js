#!/usr/bin/env node

// tools/ai-startup-fix-agent/startup-fix.js

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { runStartupFixAgent } from "./agent.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// CLI-Argumente
const args = process.argv.slice(2);

if (args.length === 0) {
    console.error("❌ Bitte ein Log oder eine Log-Datei angeben.");
    console.error("Beispiele:");
    console.error("  node tools/ai-startup-fix-agent/startup-fix.js \"Fehlertext\"");
    console.error("  node tools/ai-startup-fix-agent/startup-fix.js --log logs/playwright.log");
    console.error("Optionale Flags: --dry-run --no-push --verbose");
    process.exit(1);
}

// Flags
const dryRun = args.includes("--dry-run");
const noPush = args.includes("--no-push");
const verbose = args.includes("--verbose");
const outIndex = args.indexOf("--out");
const outPath = outIndex >= 0 ? args[outIndex + 1] : null;

// Flags aus args entfernen
const filteredArgs = args.filter(
    a => !["--dry-run", "--no-push", "--verbose", "--out"].includes(a)
);

let logContent = "";

// Option 1: --log <file>
if (filteredArgs[0] === "--log") {
    const filePath = filteredArgs[1];
    if (!filePath) {
        console.error("❌ Bitte eine Log-Datei angeben.");
        process.exit(1);
    }

    const absPath = path.resolve(process.cwd(), filePath);

    if (!fs.existsSync(absPath)) {
        console.error(`❌ Log-Datei nicht gefunden: ${absPath}`);
        process.exit(1);
    }

    logContent = fs.readFileSync(absPath, "utf8");
    console.log(`📄 Log-Datei geladen: ${absPath}`);
} else {
    // Option 2: Direktes Log als String
    logContent = filteredArgs.join(" ");
    console.log("📄 Log aus CLI-Argumenten geladen.");
}

(async () => {
    const result = await runStartupFixAgent(logContent, {
        dryRun,
        noPush,
        verbose
    });

    console.log("\n===== 🧠 AI Startup Fix Agent Ergebnis =====");
    console.log(`Problem:         ${result.issue}`);
    console.log(`Strategie:       ${result.strategy}`);
    console.log(`Patch angewandt: ${result.patchApplied}`);
    console.log(`Commit erstellt: ${result.committed}`);
    console.log(`Push ausgeführt: ${result.pushed}`);
    console.log("================================================\n");

    if (outPath) {
        const absOut = path.resolve(process.cwd(), outPath);
        fs.mkdirSync(path.dirname(absOut), { recursive: true });
        fs.writeFileSync(absOut, JSON.stringify(result, null, 2), "utf8");
        if (verbose) {
            console.log(`🧾 Ergebnis geschrieben: ${absOut}`);
        }
    }

    if (result.patchApplied && result.committed) {
        console.log("🚀 Fix erfolgreich angewendet.");
    } else {
        console.log("⚠️  Fix konnte nicht vollständig ausgeführt werden.");
    }
})();
