const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Language mapping (same as before)
const LANGUAGE_MAP = {
  '.js': 'JavaScript', '.ts': 'TypeScript',
  '.py': 'Python', '.java': 'Java', '.go': 'Go',
  '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
  '.cs': 'C#', '.cpp': 'C++', '.c': 'C',
  '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS',
  '.json': 'JSON', '.yaml': 'YAML', '.yml': 'YAML',
  '.md': 'Markdown', '.sh': 'Shell', '.sql': 'SQL',
  '.txt': 'Text'
};
const UNKNOWN = 'Other';

function detectLanguage(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return LANGUAGE_MAP[ext] || UNKNOWN;
}

function getChangedFiles() {
  // GitHub Actions checkout@v4 uses a shallow fetch by default.
  // We need to get the difference between the current commit and the previous one.
  const baseSha = process.env.GITHUB_BASE_REF ? 
    execSync(`git merge-base origin/${process.env.GITHUB_BASE_REF} HEAD`).toString().trim() :
    `${process.env.GITHUB_SHA}^`;  // previous commit for push events
  
  const cmd = `git diff --name-only ${baseSha} ${process.env.GITHUB_SHA}`;
  const output = execSync(cmd, { encoding: 'utf8' });
  return output.split('\n').filter(f => f.trim().length > 0);
}

function generateSVG(languageCounts, totalFiles) {
  const width = 600;
  const barHeight = 30;
  const labelWidth = 150;
  const barAreaWidth = width - labelWidth - 80;
  const startY = 50;
  const rowHeight = barHeight + 10;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${startY + Object.keys(languageCounts).length * rowHeight + 20}">
  <rect width="100%" height="100%" fill="#f9f9f9" rx="10"/>
  <text x="20" y="30" font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="#333">Commit Language Breakdown</text>`;

  let y = startY;
  for (const [lang, count] of Object.entries(languageCounts)) {
    const percent = ((count / totalFiles) * 100).toFixed(1);
    const barWidth = (count / totalFiles) * barAreaWidth;
    svg += `
  <text x="20" y="${y + 20}" font-family="monospace" font-size="14" fill="#555">${lang}</text>
  <rect x="${labelWidth + 10}" y="${y + 5}" width="${barWidth}" height="${barHeight}" fill="#4c9aff" rx="4"/>
  <text x="${labelWidth + barWidth + 20}" y="${y + 20}" font-family="monospace" font-size="14" fill="#333">${count} files (${percent}%)</text>`;
    y += rowHeight;
  }
  svg += `\n</svg>`;
  return svg;
}

async function run() {
  try {
    console.log('Fetching changed files...');
    const files = getChangedFiles();
    if (files.length === 0) {
      console.log('No changed files found.');
      return;
    }
    console.log(`Found ${files.length} changed files.`);

    // Count languages
    const langCount = {};
    for (const file of files) {
      const lang = detectLanguage(file);
      langCount[lang] = (langCount[lang] || 0) + 1;
    }

    const total = Object.values(langCount).reduce((a,b) => a+b, 0);
    console.log('Language counts:', langCount);

    // Generate SVG
    const svg = generateSVG(langCount, total);
    const outputPath = path.join(process.env.GITHUB_WORKSPACE || process.cwd(), 'language-breakdown.svg');
    fs.writeFileSync(outputPath, svg);
    console.log(`SVG saved to ${outputPath}`);

    // Optional: set output for later steps (if you want to use GitHub Actions outputs)
    if (process.env.GITHUB_OUTPUT) {
      fs.appendFileSync(process.env.GITHUB_OUTPUT, `svg-path=${outputPath}\n`);
      fs.appendFileSync(process.env.GITHUB_OUTPUT, `language-stats=${JSON.stringify(langCount)}\n`);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

run();
