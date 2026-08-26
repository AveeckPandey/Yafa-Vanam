import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

// This deliberately scans only Git-tracked files. Local .env files are ignored
// by Git and must never be read, logged, or sent to Jenkins.
const files = execFileSync("git", ["ls-files", "-z"], { encoding: "buffer" })
  .toString("utf8")
  .split("\0")
  .filter(Boolean)
  .filter((file) => !file.endsWith(".example") && !file.startsWith("docs/") && !file.startsWith("data/"));

const findings = [];
const rules = [
  ["AWS access key", /\bAKIA[0-9A-Z]{16}\b/g],
  ["GitHub token", /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/g],
  ["private key", /-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----/g],
  ["Razorpay live secret", /RAZORPAY_KEY_SECRET\s*[=:]\s*["']?(?!xxx\b|<)[A-Za-z0-9_\-]{16,}/gi],
];

for (const file of files) {
  const content = readFileSync(file);
  if (content.includes(0)) continue;
  const text = content.toString("utf8");
  for (const [name, expression] of rules) {
    expression.lastIndex = 0;
    const match = expression.exec(text);
    if (!match) continue;
    const line = text.slice(0, match.index).split("\n").length;
    findings.push(`${file}:${line} — possible ${name}`);
  }
}

if (findings.length) {
  console.error("Potential committed secrets found:\n" + findings.join("\n"));
  process.exit(1);
}

console.log(`Secret scan passed: ${files.length} tracked files checked.`);
