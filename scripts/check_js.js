const fs = require('fs');
const html = fs.readFileSync('frontend/index.html', 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) {
  console.log('no script');
  process.exit(1);
}
try {
  new Function(m[1]);
  console.log('JS syntax OK');
} catch (e) {
  console.log('JS SYNTAX ERROR:', e.message);
  console.log('line approx:', e.lineNumber);
}
