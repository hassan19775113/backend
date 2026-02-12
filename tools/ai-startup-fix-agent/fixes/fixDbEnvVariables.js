// tools/ai-startup-fix-agent/fixes/fixDbEnvVariables.js

import fs from "fs";

export function applyFixDbEnvVariables(workflowPath) {
    const content = fs.readFileSync(workflowPath, "utf8");

    const hasDatabaseUrl = content.includes("DATABASE_URL=") || content.includes("DATABASE_URL=");
    const hasPostgresPort = content.includes("POSTGRES_PORT=");
    const looksConfigured = content.includes("Configure Postgres env") && hasDatabaseUrl && hasPostgresPort;

    if (looksConfigured) {
        console.log("ℹ️  Workflow already configures POSTGRES_PORT and DATABASE_URL.");
        return false;
    }

    console.log("⚠️  Workflow DB env wiring not detected; manual review recommended.");
    return false;
}
