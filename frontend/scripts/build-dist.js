// Produces frontend/dist/: a byte-for-byte mirror of frontend/ except every .css/.js file is
// minified in place (same filename, same relative path) — so no HTML <link>/<script> reference
// has to change between source and build output. Source (frontend/) stays served as-is for dev
// (see README's non-Docker instructions); dist/ is what the frontend Docker image serves.
const fs = require('fs');
const path = require('path');
const esbuild = require('esbuild');

const ROOT = path.join(__dirname, '..');
const DIST = path.join(ROOT, 'dist');

const SKIP_DIRS = new Set(['node_modules', 'dist', 'scripts']);
const SKIP_FILES = new Set(['package.json', 'package-lock.json', 'tailwind.config.js', '.gitignore']);
// Tailwind's source file — only tailwind.build.css (the compiled output) ships.
const SKIP_PATHS = new Set([path.join('shared', 'css', 'tailwind.css')]);

let cssIn = 0, cssOut = 0, jsIn = 0, jsOut = 0, filesCopied = 0;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      walk(path.join(dir, entry.name));
      continue;
    }
    if (SKIP_FILES.has(entry.name)) continue;

    const srcPath = path.join(dir, entry.name);
    const relPath = path.relative(ROOT, srcPath);
    if (SKIP_PATHS.has(relPath)) continue;

    const destPath = path.join(DIST, relPath);
    fs.mkdirSync(path.dirname(destPath), { recursive: true });

    if (entry.name.endsWith('.css')) {
      const src = fs.readFileSync(srcPath, 'utf8');
      const result = esbuild.transformSync(src, { loader: 'css', minify: true });
      fs.writeFileSync(destPath, result.code);
      cssIn += src.length;
      cssOut += result.code.length;
    } else if (entry.name.endsWith('.js')) {
      const src = fs.readFileSync(srcPath, 'utf8');
      // No bundling: these are plain (non-module) scripts that declare globals consumed by
      // other, separately-loaded <script> tags (login(), toggleTheme(), api, ...) — bundling
      // or IIFE-wrapping would break that.
      const result = esbuild.transformSync(src, { loader: 'js', minify: true });
      fs.writeFileSync(destPath, result.code);
      jsIn += src.length;
      jsOut += result.code.length;
    } else {
      fs.copyFileSync(srcPath, destPath);
      filesCopied++;
    }
  }
}

fs.rmSync(DIST, { recursive: true, force: true });
walk(ROOT);

const pct = (a, b) => (a ? (100 * (1 - b / a)).toFixed(1) : '0.0');
console.log(`CSS: ${cssIn} -> ${cssOut} bytes (${pct(cssIn, cssOut)}% smaller)`);
console.log(`JS:  ${jsIn} -> ${jsOut} bytes (${pct(jsIn, jsOut)}% smaller)`);
console.log(`Other files copied as-is: ${filesCopied}`);
console.log(`Output: ${DIST}`);
