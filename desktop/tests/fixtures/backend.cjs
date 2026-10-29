const http = require('node:http');
const port = Number(process.argv[process.argv.indexOf('--port') + 1]);
if (process.env.FIXTURE_EXIT) process.exit(7);
if (process.env.FIXTURE_LOG_TOKEN) console.log(process.env.MSR_DESKTOP_TOKEN);
const server = http.createServer((request, response) => {
  if (request.headers['x-mini-six-ren-token'] !== process.env.MSR_DESKTOP_TOKEN) {
    response.writeHead(403).end();
    return;
  }
  response.setHeader('Content-Type', 'application/json');
  response.end(JSON.stringify({ application: process.env.FIXTURE_WRONG_APP ? 'other' : 'mini-six-ren-desktop', protocol: 1 }));
});
server.listen(port, '127.0.0.1');
if (process.env.FIXTURE_IGNORE_TERM) process.on('SIGTERM', () => {});
process.stdin.resume();
process.stdin.on('end', () => process.exit(0));
