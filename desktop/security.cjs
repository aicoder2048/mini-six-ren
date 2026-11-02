const THEMES = Object.freeze(['paper', 'night', 'ink', 'neon']);

function isBackendUrl(value, origin) {
  try {
    const url = new URL(value);
    return !url.username && !url.password &&
      (url.protocol === 'http:' || url.protocol === 'ws:') &&
      url.host === new URL(origin).host;
  } catch { return false; }
}

function isExternalUrl(value) {
  try { return ['https:', 'http:'].includes(new URL(value).protocol); }
  catch { return false; }
}

module.exports = { THEMES, isBackendUrl, isExternalUrl };
