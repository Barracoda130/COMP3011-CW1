const DEFAULT_TTL_MS = 5 * 60 * 1000;
const DEFAULT_MAX_BYTES = 1_200_000;

function byteSize(value) {
  try {
    return new TextEncoder().encode(value).length;
  } catch {
    return value.length;
  }
}

function clonePayload(payload) {
  return JSON.parse(JSON.stringify(payload));
}

function trimLargeArrays(payload) {
  const candidateKeys = ["cachedResults", "cachedItems", "items"];
  let trimmed = false;

  for (const key of candidateKeys) {
    if (!Array.isArray(payload[key])) {
      continue;
    }

    if (payload[key].length <= 40) {
      continue;
    }

    payload[key] = payload[key].slice(0, Math.max(40, Math.floor(payload[key].length * 0.7)));
    trimmed = true;
  }

  return trimmed;
}

export function saveSessionPageCache(key, payload, options = {}) {
  const maxBytes = options.maxBytes ?? DEFAULT_MAX_BYTES;

  let wrapped = {
    savedAt: Date.now(),
    payload: clonePayload(payload)
  };

  let encoded = JSON.stringify(wrapped);
  let attempts = 0;
  while (byteSize(encoded) > maxBytes && attempts < 6) {
    const changed = trimLargeArrays(wrapped.payload);
    if (!changed) {
      break;
    }
    encoded = JSON.stringify(wrapped);
    attempts += 1;
  }

  if (byteSize(encoded) > maxBytes) {
    sessionStorage.removeItem(key);
    return false;
  }

  sessionStorage.setItem(key, encoded);
  return true;
}

export function loadSessionPageCache(key, options = {}) {
  const ttlMs = options.ttlMs ?? DEFAULT_TTL_MS;

  const raw = sessionStorage.getItem(key);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.savedAt !== "number" || typeof parsed.payload !== "object") {
      sessionStorage.removeItem(key);
      return null;
    }

    if (Date.now() - parsed.savedAt > ttlMs) {
      sessionStorage.removeItem(key);
      return null;
    }

    return parsed.payload;
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}
