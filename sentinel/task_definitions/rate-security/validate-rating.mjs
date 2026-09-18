/**
 * Validate (and repair) the candidate rating JSON, then write the canonical rating file.
 *
 * Reads the model output, strips fences / extracts embedded JSON / repairs JSON as
 * needed, and enforces the exact shape: keys {symbol, rating, rationale}, symbol matches,
 * rating a finite 0..1 number, and a non-empty rationale. On success
 * writes rating.json and prints {valid:true,...}; on failure prints {valid:false, error,
 * schema, raw} so the rating loop can retry with the feedback.
 *
 * Environment: SENTINEL_APP_ROOT, CONTEXT_JSON (resolve-rating-context output).
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const appRoot = process.env.SENTINEL_APP_ROOT;
if (!appRoot) throw new Error('SENTINEL_APP_ROOT is required');
const appRequire = createRequire(import.meta.url);
const { jsonrepair } = appRequire(join(appRoot, 'sentinel/tasks/vendor/jsonrepair.cjs'));

const ctx = JSON.parse(process.env.CONTEXT_JSON);
const expectedSymbol = ctx.symbol;
const rawPath = ctx.ratingRawPath;
const ratingPath = ctx.ratingPath;
const schema = {
  type: 'object',
  additionalProperties: false,
  required: ['symbol', 'rating', 'rationale'],
  properties: {
    symbol: expectedSymbol,
    rating: 'number from 0.0 to 1.0',
    rationale: 'non-empty string',
  },
};

let raw = '';
try {
  raw = await readFile(rawPath, 'utf8');
  const value = normalizeJsonOutput(raw);
  const canonical = validateRating(value);
  await mkdir(dirname(ratingPath), { recursive: true });
  await writeFile(ratingPath, JSON.stringify(canonical, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify({ valid: true, canonical_path: ratingPath, raw_path: rawPath, canonical }));
} catch (error) {
  console.log(JSON.stringify({
    valid: false,
    error: errorMessage(error),
    raw_path: rawPath,
    canonical_path: ratingPath,
    schema,
    raw: raw.length > 12000 ? raw.slice(0, 12000) + '\n...[truncated]' : raw,
  }));
}

function normalizeJsonOutput(input) {
  const trimmed = stripJsonFence(String(input ?? '').trim());
  if (!trimmed) throw new Error('rating.raw.json is empty');
  try {
    return JSON.parse(trimmed);
  } catch (originalError) {
    const embedded = embeddedJson(trimmed);
    const candidate = embedded ?? trimmed;
    const candidateStart = candidate.trimStart()[0];
    if (!embedded && candidateStart !== '{' && candidateStart !== '[') throw originalError;
    try {
      return JSON.parse(jsonrepair(candidate));
    } catch {
      throw originalError;
    }
  }
}

function validateRating(value) {
  if (!isRecord(value)) throw new Error('Rating JSON must be an object');
  const keys = Object.keys(value).sort();
  const expectedKeys = ['rating', 'rationale', 'symbol'];
  if (JSON.stringify(keys) !== JSON.stringify(expectedKeys)) {
    throw new Error('Rating JSON must contain exactly ' + expectedKeys.join(', '));
  }
  const symbol = stringValue(value.symbol);
  if (symbol !== expectedSymbol) throw new Error('Rating symbol must be ' + expectedSymbol);
  const rating = value.rating;
  if (typeof rating !== 'number' || !Number.isFinite(rating) || rating < 0 || rating > 1) {
    throw new Error('Rating must be a finite number from 0.0 to 1.0');
  }
  const rationale = stringValue(value.rationale);
  if (!rationale) throw new Error('Rationale is required');
  return { symbol, rating, rationale };
}

function stripJsonFence(input) {
  const match = input.match(/^```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```$/i);
  return match ? match[1].trim() : input;
}

function embeddedJson(input) {
  const objectStart = input.indexOf('{');
  const arrayStart = input.indexOf('[');
  const starts = [objectStart, arrayStart].filter((index) => index >= 0);
  if (starts.length === 0) return null;
  const start = Math.min(...starts);
  const end = Math.max(input.lastIndexOf('}'), input.lastIndexOf(']'));
  if (end < start) return null;
  return input.slice(start, end + 1).trim();
}

function stringValue(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}
