// tools/ai-fix-agent.js
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import OpenAI from 'openai';

const logPath = process.argv[2];
const client = new OpenAI({ apiKey: process.env.AI_API_KEY });

// Konfiguration für V2
const MAX_ITERATIONS = 3;
const MAX_PATCH_LINES = 200;
const ALLOWED_PATH_PREFIXES = ['tests/', 'playwright.config.ts'];

async function main() {
  if (!logPath) {
    console.error('❌ Kein Log-Pfad übergeben.');
    process.exit(1);
  }

  if (!process.env.AI_API_KEY) {
    console.error('❌ AI_API_KEY ist nicht gesetzt.');
    process.exit(1);
  }

  console.log('🔍 AI Fix Agent V2 gestartet');
  const testLog = fs.readFileSync(logPath, 'utf8');

  const targetDirs = [
    'tests/e2e',
    'tests/pages',
    'tests/fixtures',
    'tests/utils',
  ];

  const files = collectFiles(targetDirs);
  if (fs.existsSync('playwright.config.ts')) {
    files.push('playwright.config.ts');
  }

  const fileContents = {};
  for (const f of files) {
    fileContents[f] = fs.readFileSync(f, 'utf8');
  }

  const diagnostics = extractDiagnostics(testLog);

  for (let iteration = 1; iteration <= MAX_ITERATIONS; iteration++) {
    console.log(`\n🔁 Iteration ${iteration}/${MAX_ITERATIONS}`);

    const prompt = buildPrompt(testLog, fileContents, diagnostics, iteration);

    console.log('🤖 Frage GPT‑4.1‑mini nach einem Patch…');
    let patch = await askLLM(prompt, 'gpt-4.1-mini');

    if (!isValidPatch(patch)) {
      console.log('⚠️ mini konnte keinen gültigen Patch liefern. Versuche GPT‑4.1…');
      patch = await askLLM(prompt, 'gpt-4.1');
    }

    if (!isValidPatch(patch)) {
      console.log('❌ Kein gültiger Patch generiert. Breche ab.');
      process.exit(1);
    }

    patch = extractPurePatch(patch);

    if (!isPatchSafe(patch)) {
      console.log('⚠️ Patch verletzt Sicherheitsregeln (Größe/Pfade). Breche ab.');
      process.exit(1);
    }

    console.log('📦 Patch erhalten, prüfe Anwendbarkeit…');
    fs.writeFileSync('ai-fix.patch', patch);

    try {
      execSync('git apply --check ai-fix.patch', { stdio: 'inherit' });
    } catch {
      console.error('❌ Patch lässt sich nicht sauber anwenden. Breche ab.');
      process.exit(1);
    }

    console.log('✅ Patch ist gültig, wende ihn an…');
    execSync('git apply ai-fix.patch', { stdio: 'inherit' });

    try {
      console.log('🧪 Starte Playwright-Tests nach Fix…');
      execSync('npx playwright test', { stdio: 'inherit' });
      console.log('✅ Tests nach AI-Fix grün, committe Änderungen…');

      execSync('git config user.name "ai-fix-bot"');
      execSync('git config user.email "ai-fix-bot@example.com"');
      execSync('git commit -am "AI fix agent: auto-fix"');
      execSync('git push origin HEAD:ai-fix');

      console.log('🚀 Erfolgreich abgeschlossen.');
      process.exit(0);
    } catch {
      console.error('❌ Tests nach Patch immer noch rot.');
      // Neue Iteration, falls noch welche übrig sind
    }
  }

  console.error('⛔ Maximalanzahl an Iterationen erreicht, ohne grüne Tests.');
  process.exit(1);
}

function collectFiles(dirs) {
  const result = [];
  for (const dir of dirs) {
    if (!fs.existsSync(dir)) continue;
    walk(dir, result);
  }
  return result;
}

function walk(dir, result) {
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (fs.statSync(full).isDirectory()) walk(full, result);
    else if (full.endsWith('.ts')) result.push(full);
  }
}

function extractDiagnostics(testLog) {
  const lines = testLog.split('\n');
  const selectorErrors = [];
  const timeoutErrors = [];
  const poErrors = [];

  for (const line of lines) {
    if (line.includes('Timeout') && line.includes('exceeded')) {
      timeoutErrors.push(line.trim());
    }
    if (line.includes('strict mode violation') || line.includes('locator(')) {
      selectorErrors.push(line.trim());
    }
    if (line.includes('TypeError') || line.includes('Cannot read properties')) {
      poErrors.push(line.trim());
    }
  }

  return { selectorErrors, timeoutErrors, poErrors };
}

function buildPrompt(testLog, files, diagnostics, iteration) {
  const { selectorErrors, timeoutErrors, poErrors } = diagnostics;

  return `
Du bist ein Senior QA/Automation Engineer für PraxiApp.
Deine Aufgabe: Behebe Playwright-Testfehler, ohne Business-Logik zu ändern.

Iteration: ${iteration}/${MAX_ITERATIONS}

Regeln:
- Ändere nur Dateien unter tests/** oder playwright.config.ts
- Nutze Playwright Best Practices (locator, expect, waits)
- Fixe Selektoren, Page Objects, Fixtures, Imports, Timeouts
- Halte Änderungen minimal und zielgerichtet
- Gib NUR einen Unified-Diff-Patch zurück (git diff --no-index Format)
- KEIN Text außerhalb des Patches, KEIN Markdown, KEINE Erklärungen

Fehler-Diagnose:
Selector-Fehler:
${selectorErrors.join('\n') || 'Keine expliziten Selector-Fehler erkannt.'}

Timeout-Fehler:
${timeoutErrors.join('\n') || 'Keine expliziten Timeout-Fehler erkannt.'}

Page-Object-/Runtime-Fehler:
${poErrors.join('\n') || 'Keine expliziten PO-Fehler erkannt.'}

Test-Log (gekürzt, aber vollständig übergeben):
${testLog}

Relevante Dateien:
${Object.entries(files)
  .map(([name, content]) => `Datei: ${name}\n\n${content}`)
  .join('\n\n---\n\n')}
`;
}

async function askLLM(prompt, model) {
  try {
    const response = await client.responses.create({
      model,
      input: prompt,
    });
    const text = response.output_text;
    return text || '';
  } catch (err) {
    console.error(`❌ Fehler beim LLM (${model}):`, err.message || err);
    return '';
  }
}

function isValidPatch(patch) {
  if (!patch) return false;
  return patch.includes('diff --git') || (patch.includes('---') && patch.includes('+++'));
}

function extractPurePatch(raw) {
  let text = raw.trim();

  // Markdown-Codeblöcke entfernen
  if (text.startsWith('```')) {
    const first = text.indexOf('```');
    const last = text.lastIndexOf('```');
    if (last > first) {
      text = text.slice(first + 3, last).trim();
    }
  }

  // Nur ab diff --git nehmen, falls vorhanden
  const idx = text.indexOf('diff --git');
  if (idx !== -1) {
    text = text.slice(idx);
  }

  return text.trim();
}

function isPatchSafe(patch) {
  const lines = patch.split('\n');
  if (lines.length > MAX_PATCH_LINES) {
    console.log(`⚠️ Patch zu groß: ${lines.length} Zeilen (max ${MAX_PATCH_LINES}).`);
    return false;
  }

  const touchedFiles = new Set();
  for (const line of lines) {
    if (line.startsWith('+++ ') || line.startsWith('--- ')) {
      const parts = line.split(' ');
      const file = parts[1]?.replace(/^a\//, '').replace(/^b\//, '');
      if (file) touchedFiles.add(file);
    }
  }

  for (const f of touchedFiles) {
    if (!ALLOWED_PATH_PREFIXES.some((prefix) => f === prefix || f.startsWith(prefix))) {
      console.log(`⚠️ Patch betrifft nicht erlaubte Datei: ${f}`);
      return false;
    }
  }

  return true;
}

main().catch((e) => {
  console.error('❌ Unerwarteter Fehler im Agent:', e);
  process.exit(1);
});
