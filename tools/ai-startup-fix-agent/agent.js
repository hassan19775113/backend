// tools/ai-startup-fix-agent/agent.js

import { detectIssue } from "./logParser.js";
import { getFixStrategy } from "./strategy.js";
import { applyPatch } from "./patcher.js";

// Fix-Module
import { applyFixAuthSetup } from "./fixes/fixAuthSetup.js";
import { applyFixDbEnvVariables } from "./fixes/fixDbEnvVariables.js";
import { applyFixDjangoSettings } from "./fixes/fixDjangoSettings.js";

/**
 * @param {string} log
 * @param {{dryRun?: boolean, noPush?: boolean, verbose?: boolean, workflowPath?: string}} options
 */
export async function runStartupFixAgent(log, options = {}) {
    const {
        dryRun = false,
        noPush = false,
        verbose = false,
        workflowPath = ".github/workflows/backend-setup.yml"
    } = options;

    console.log("🚀 Starte AI Startup Fix Agent...");
    if (verbose) {
        console.log("🔧 Optionen:", options);
    }

    console.log("🔍 Analysiere Log...");
    const issue = detectIssue(log);
    console.log(`➡️  Erkanntes Problem: ${issue}`);

    const strategy = getFixStrategy(issue);
    console.log(`➡️  Strategie: ${strategy.type} – ${strategy.description}`);

    let patchApplied = false;

    // 3. Fix ausführen
    switch (strategy.type) {
        case "FIX_AUTH_SETUP": {
            console.log("🛠  Repariere auth.setup.ts...");
            const authSetupPath = "tests/fixtures/auth.setup.ts";

            if (dryRun) {
                console.log(`🟨 Dry-Run aktiv – Datei würde repariert: ${authSetupPath}`);
                patchApplied = true;
            } else {
                patchApplied = applyFixAuthSetup(authSetupPath);
            }
            break;
        }

        case "FIX_DB_ENV_VARIABLES": {
            console.log("🛠  Korrigiere DB-ENV-Variablen im Workflow...");
            if (dryRun) {
                console.log(`🟨 Dry-Run aktiv – ENV-Patch würde in ${workflowPath} eingefügt.`);
                patchApplied = true;
            } else {
                patchApplied = applyFixDbEnvVariables(workflowPath);
            }
            break;
        }

        case "FIX_DJANGO_SETTINGS_MODULE": {
            console.log("🛠  Repariere Django Settings im Workflow...");
            if (dryRun) {
                console.log(`🟨 Dry-Run aktiv – Django-Settings-Patch würde in ${workflowPath} eingefügt.`);
                patchApplied = true;
            } else {
                patchApplied = applyFixDjangoSettings(workflowPath);
            }
            break;
        }

        default:
            console.log("⚠️  Kein implementiertes Fix-Modul für diese Strategie.");
            return {
                issue,
                strategy: strategy.type,
                patchApplied: false,
                committed: false,
                pushed: false
            };
    }

    if (!patchApplied) {
        console.log("⚠️  Patch wurde nicht angewendet. Kein Commit.");
        return {
            issue,
            strategy: strategy.type,
            patchApplied: false,
            committed: false,
            pushed: false
        };
    }

    if (dryRun) {
        console.log("🟨 Dry-Run aktiv – keine Git-Operationen.");
        return {
            issue,
            strategy: strategy.type,
            patchApplied: true,
            committed: false,
            pushed: false
        };
    }

    if (noPush) {
        console.log("🟨 noPush aktiv – keine Git-Operationen.");
    }

    return {
        issue,
        strategy: strategy.type,
        patchApplied: true,
        committed: false,
        pushed: false
    };
}
