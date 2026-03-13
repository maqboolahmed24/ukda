#!/usr/bin/env node
/* global console, process */

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const TARGETS = [
  "web/app/globals.css",
  "web/components",
  "web/app/(authenticated)/admin/design-system/page.tsx"
];
const FILE_PATTERN = /\.(css|ts|tsx)$/;
const COLOR_LITERAL_PATTERN =
  /#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)/g;

function walk(targetPath) {
  const absolutePath = path.resolve(ROOT, targetPath);
  const stats = statSync(absolutePath);
  if (stats.isFile()) {
    return [absolutePath];
  }

  const files = [];
  for (const entry of readdirSync(absolutePath)) {
    const childPath = path.join(absolutePath, entry);
    const childStats = statSync(childPath);
    if (childStats.isDirectory()) {
      files.push(...walk(childPath));
      continue;
    }
    if (FILE_PATTERN.test(childPath)) {
      files.push(childPath);
    }
  }
  return files;
}

function resolveLineNumber(source, index) {
  return source.slice(0, index).split("\n").length;
}

const violations = [];

for (const target of TARGETS) {
  for (const file of walk(target)) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(COLOR_LITERAL_PATTERN)) {
      if (typeof match.index !== "number") {
        continue;
      }
      const line = resolveLineNumber(source, match.index);
      const literal = match[0];
      violations.push({
        file: path.relative(ROOT, file),
        line,
        literal
      });
    }
  }
}

if (violations.length > 0) {
  console.error(
    "Design-token guardrail failed. Replace raw color literals with /packages/ui tokens:"
  );
  for (const violation of violations) {
    console.error(
      `- ${violation.file}:${violation.line} -> ${violation.literal}`
    );
  }
  process.exit(1);
}

console.log("Design-token guardrail passed.");
