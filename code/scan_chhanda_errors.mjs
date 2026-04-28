// scan_chhanda_errors.mjs
// Scans verses in a text for meter (chhanda) based typos.
// Usage: node scan_chhanda_errors.mjs <textname> [<textname2> ...]
//        node scan_chhanda_errors.mjs --all
//
// For each verse identified as a samavṛtta (all 4 pādas have the same syllable-weight
// pattern), checks whether all 4 pādas actually match. Discrepancies indicate typos.
// Outputs a JSON array of flagged verses to stdout.

import { MeterIdentifier } from 'skrutable-js';
import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_ROOT = join(__dirname, '..');

// Samavṛtta names as defined in skrutable-js meter_patterns.js (v2.1.x).
// All 4 pādas of a samavṛtta share an identical syllable-weight pattern,
// so any pāda that deviates from the consensus pattern indicates a typo.
const SAMAVRTTAS = new Set([
  'kanyā', 'paṅktiḥ', 'tanumadhyamā', 'vidyullekhā', 'śaśivadanā', 'somarājī',
  'kumāralalitā', 'madalekhā', 'madhumatī', 'gajagatiḥ', 'pramāṇikā', 'māṇavakam',
  'vidyumālā', 'bhujagaśiṣubhṛtā', 'bhujaṅgasaṅgatā', 'maṇimadhyam', 'tvaritagatiḥ',
  'mattā', 'rukmavatī', 'indravajrā', 'upendravajrā', 'dodhakam', 'bhramaravilasitam',
  'rathoddhatā', 'vātormī', 'śālinī', 'svāgatā', 'indravaṃśā', 'candravatmam',
  'jaladharamālā', 'jaloddhatagatiḥ', 'tāmarasam', 'toṭakam', 'drutavilambitam',
  'pramuditavadanā', 'pramitākṣarā', 'bhujaṅgaprayātam', 'maṇimālā', 'mālatī',
  'vaṃśastham', 'vaiśvadevī', 'sragviṇī', 'kalahaṃsam', 'kṣamā', 'praharṣiṇī',
  'mañjubhāṣiṇī', 'mattamayūram', 'rucirā', 'aparājitā', 'asaṃbādhā', 'pathyā',
  'pramadā', 'praharaṇakalikā', 'madhyakṣāmā', 'vasantatilakā', 'vāsantī',
  'cārucāmaram', 'mālinī', 'līlākhelam', 'śaśikalā', 'citram', 'pañcacāmaram',
  'vāṇinī', 'citralekhā', 'narkuṭaka', 'pṛthvī', 'mandākrāntā', 'vaṃśapatrapatitam',
  'śikhariṇī', 'hariṇī', 'kusumitalatāvellitā', 'nandanam', 'nārācam',
  'śārdūlalalitam', 'mallikāmālā', 'meghavisphūrjitā', 'śārdūlavikrīḍitam',
  'sumadhurā', 'surasā', 'gītikā', 'suvadanā', 'pañcakāvalī', 'sragdharā',
  'haṃsī', 'aśvadhāṭī', 'adritanayā', 'śravaṇābharaṇam', 'tanvī', 'krauñcapadā',
  'bhujaṅgavijṛmbhitam', 'śivatāṇḍavam',
]);

const SKIP = new Set(['code', 'dhatu', 'kosha', 'chhanda', 'ashtadhyayi', 'sahityadarpanam']);

function extractMeterName(label) {
  if (!label) return null;
  const m = label.match(/^([^[(]+)/);
  return m ? m[1].trim() : label.trim();
}

// Compare all 4 pādas ignoring the final syllable (which is traditionally anceps).
// Returns { expected, padaWeights, mismatches } or null if the verse isn't 4-pāda.
function analysePadaWeights(syllableWeights) {
  const lines = syllableWeights.split('\n').filter(Boolean);
  if (lines.length !== 4) return null;

  // Trim last syllable from each pāda before comparison
  const trimmed = lines.map(l => l.slice(0, -1));

  const freq = {};
  for (const l of trimmed) freq[l] = (freq[l] || 0) + 1;
  const expectedTrimmed = trimmed.reduce((best, l) =>
    freq[l] > freq[best] || (freq[l] === freq[best] && trimmed.indexOf(l) < trimmed.indexOf(best))
      ? l : best
  );

  const mismatches = [];
  for (let i = 0; i < 4; i++) {
    if (trimmed[i] === expectedTrimmed) continue;
    const diffPositions = [];
    const len = Math.min(trimmed[i].length, expectedTrimmed.length);
    for (let j = 0; j < len; j++) {
      if (trimmed[i][j] !== expectedTrimmed[j]) diffPositions.push(j);
    }
    if (trimmed[i].length !== expectedTrimmed.length) {
      diffPositions.push(`length:${trimmed[i].length}vs${expectedTrimmed.length}`);
    }
    mismatches.push({ padaIndex: i, actual: lines[i], diffPositions });
  }

  // Append '?' to show the final syllable is anceps
  return { expected: expectedTrimmed + '?', padaWeights: lines, mismatches };
}

function loadTextData(textName) {
  const dir = join(DATA_ROOT, textName);
  if (!existsSync(dir)) return [];
  const files = readdirSync(dir).filter(f => f.endsWith('.json')).sort();
  const verses = [];
  for (const file of files) {
    const raw = JSON.parse(readFileSync(join(dir, file), 'utf8'));
    for (const entry of (raw.data || [])) {
      if (typeof entry === 'object' && entry !== null && typeof entry.v === 'string') {
        verses.push({ file, entry });
      }
    }
  }
  return verses;
}

function getAllTextNames() {
  return readdirSync(DATA_ROOT).filter(name => {
    if (SKIP.has(name)) return false;
    const path = join(DATA_ROOT, name);
    try { return readdirSync(path).some(f => f.endsWith('.json')); }
    catch { return false; }
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node scan_chhanda_errors.mjs <textname> [<textname2> ...] | --all');
    process.exit(1);
  }

  const textNames = args[0] === '--all' ? getAllTextNames() : args;
  const MI = new MeterIdentifier();
  const results = [];

  for (const textName of textNames) {
    process.stderr.write(`Scanning ${textName}...\n`);
    const verses = loadTextData(textName);
    if (verses.length === 0) {
      process.stderr.write(`  No verse data found for ${textName}\n`);
      continue;
    }

    let flagged = 0;
    for (const { file, entry } of verses) {
      let verseObj;
      try {
        verseObj = MI.identify_meter(entry.v, 'resplit_max', false, 'DEV');
      } catch (e) {
        process.stderr.write(`  Error on ${textName}/${entry.n}: ${e.message}\n`);
        continue;
      }

      const meterName = extractMeterName(verseObj.meterLabel);
      if (!meterName || !SAMAVRTTAS.has(meterName)) continue;
      if (!verseObj.syllableWeights) continue;

      const analysis = analysePadaWeights(verseObj.syllableWeights);
      if (!analysis || analysis.mismatches.length === 0) continue;

      flagged++;
      const ctx = {};
      if (entry.anv) ctx.anv = entry.anv;
      if (entry.pc) ctx.pc = entry.pc;
      if (entry.ch) ctx.ch = entry.ch;

      // Parse textSyllabified into per-pāda syllable arrays (SLP1 tokens)
      // so the NLU step can directly identify the syllable at each mismatch position.
      const padaSyllables = verseObj.textSyllabified
        ? verseObj.textSyllabified.split('\n').filter(Boolean).map(line => line.trim().split(/\s+/))
        : null;

      const id = entry.c != null ? `${entry.c}.${entry.n}` : String(entry.n);

      results.push({
        text: textName,
        file,
        id,
        n: entry.n,
        v: entry.v,
        meter: verseObj.meterLabel,
        expected: analysis.expected,
        padaWeights: analysis.padaWeights,
        padaSyllables,
        mismatches: analysis.mismatches,
        ctx,
      });
    }
    process.stderr.write(`  Done. Flagged: ${flagged}\n`);
  }

  console.log(JSON.stringify(results, null, 2));
}

main();
