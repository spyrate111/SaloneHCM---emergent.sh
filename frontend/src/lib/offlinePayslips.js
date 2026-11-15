const DB_NAME = "salonehcm-offline-payslips";
const DB_VERSION = 1;
const STORE_NAME = "records";
const MAX_CACHED_PDFS = 12;
const encoder = new TextEncoder();
const decoder = new TextDecoder();

let dbPromise;

function openDb() {
  if (dbPromise) return dbPromise;
  if (!globalThis.indexedDB) return Promise.reject(new Error("Offline storage is not available."));
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => {
      dbPromise = null;
      reject(request.error || new Error("Could not open offline payslip storage."));
    };
    request.onblocked = () => {
      dbPromise = null;
      reject(new Error("Offline payslip storage is blocked by another tab."));
    };
  });
  return dbPromise;
}

function readAllRecords() {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readonly");
    const request = transaction.objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve(Array.isArray(request.result) ? request.result : []);
    request.onerror = () => reject(request.error || new Error("Could not read offline payslips."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline payslip read was interrupted."));
  }));
}

function readRecord(key) {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readonly");
    const request = transaction.objectStore(STORE_NAME).get(key);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error || new Error("Could not read the saved payslip."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline payslip read was interrupted."));
  }));
}

function writeRecord(record) {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).put(record);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Could not save the payslip offline."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline payslip save was interrupted."));
  }));
}

function replaceRecords(accountId, kind, records) {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readwrite");
    const store = transaction.objectStore(STORE_NAME);
    const request = store.getAll();
    request.onsuccess = () => {
      for (const item of request.result || []) {
        if (item.accountId === accountId && item.kind === kind) store.delete(item.key);
      }
      for (const record of records) store.put(record);
    };
    request.onerror = () => reject(request.error || new Error("Could not update the offline payslip list."));
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Could not update the offline payslip list."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline payslip update was interrupted."));
  }));
}

function deleteRecords(keys) {
  if (!keys.length) return Promise.resolve();
  return openDb().then((db) => new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readwrite");
    const store = transaction.objectStore(STORE_NAME);
    keys.forEach((key) => store.delete(key));
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Could not clear offline payslips."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline payslip cleanup was interrupted."));
  }));
}

async function deriveKey(token, salt) {
  if (!token || !globalThis.crypto?.subtle || !globalThis.crypto?.getRandomValues) {
    throw new Error("Encrypted offline payslip storage is not available in this browser.");
  }
  const material = await crypto.subtle.importKey(
    "raw",
    encoder.encode(String(token)),
    "HKDF",
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt,
      info: encoder.encode("salonehcm-offline-payslip-cache-v1"),
    },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function encryptOfflineBytes(value, token, context) {
  if (!globalThis.crypto?.subtle || !globalThis.crypto?.getRandomValues) {
    throw new Error("Encrypted offline payslip storage is not available in this browser.");
  }
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(token, salt);
  const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: encoder.encode(String(context)) },
    key,
    bytes,
  );
  return { salt: Array.from(salt), iv: Array.from(iv), ciphertext };
}

export async function decryptOfflineBytes(record, token, context) {
  const key = await deriveKey(token, new Uint8Array(record.salt));
  const plaintext = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: new Uint8Array(record.iv),
      additionalData: encoder.encode(String(context)),
    },
    key,
    record.ciphertext,
  );
  return new Uint8Array(plaintext);
}

function recordKey(accountId, kind, runId) {
  return `${accountId}:${kind}:${runId}`;
}

export async function saveOfflinePayslipSummaries(accountId, rows, token) {
  if (!accountId || !token || !Array.isArray(rows)) return false;
  const id = String(accountId);
  const records = await Promise.all(rows.map(async (row, sortOrder) => {
    const key = recordKey(id, "summary", row.run_id);
    const ciphertext = await encryptOfflineBytes(encoder.encode(JSON.stringify(row)), token, key);
    return {
      ...ciphertext,
      key,
      accountId: id,
      kind: "summary",
      runId: String(row.run_id),
      period: String(row.period || ""),
      sortOrder,
      savedAt: Date.now(),
    };
  }));
  await replaceRecords(id, "summary", records);
  return true;
}

export async function getOfflinePayslipSummaries(accountId, token) {
  if (!accountId || !token) return [];
  const id = String(accountId);
  const records = (await readAllRecords())
    .filter((record) => record.accountId === id && record.kind === "summary")
    .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
  const rows = [];
  const invalidKeys = [];
  for (const record of records) {
    try {
      const bytes = await decryptOfflineBytes(record, token, record.key);
      rows.push(JSON.parse(decoder.decode(bytes)));
    } catch {
      invalidKeys.push(record.key);
    }
  }
  await deleteRecords(invalidKeys);
  return rows;
}

export async function saveOfflinePayslipPdf(accountId, runId, period, blob, token) {
  if (!accountId || !runId || !blob || !token) return false;
  const id = String(accountId);
  const key = recordKey(id, "pdf", runId);
  const ciphertext = await encryptOfflineBytes(new Uint8Array(await blob.arrayBuffer()), token, key);
  await writeRecord({
    ...ciphertext,
    key,
    accountId: id,
    kind: "pdf",
    runId: String(runId),
    period: String(period || ""),
    mimeType: blob.type || "application/pdf",
    savedAt: Date.now(),
  });

  const cached = (await readAllRecords())
    .filter((record) => record.accountId === id && record.kind === "pdf")
    .sort((a, b) => b.savedAt - a.savedAt);
  await deleteRecords(cached.slice(MAX_CACHED_PDFS).map((record) => record.key));
  return true;
}

export async function getOfflinePayslipPdf(accountId, runId, token) {
  if (!accountId || !runId || !token) return null;
  const key = recordKey(String(accountId), "pdf", runId);
  const record = await readRecord(key);
  if (!record) return null;
  const bytes = await decryptOfflineBytes(record, token, key);
  return new Blob([bytes], { type: record.mimeType || "application/pdf" });
}

export async function listOfflinePayslipPdfRunIds(accountId, token) {
  if (!accountId || !token) return [];
  const id = String(accountId);
  const records = (await readAllRecords())
    .filter((record) => record.accountId === id && record.kind === "pdf");
  const valid = [];
  const invalidKeys = [];
  for (const record of records) {
    try {
      await decryptOfflineBytes(record, token, record.key);
      valid.push(record.runId);
    } catch {
      invalidKeys.push(record.key);
    }
  }
  await deleteRecords(invalidKeys);
  return valid;
}

export async function clearOfflinePayslips(accountId) {
  if (!accountId) return;
  const id = String(accountId);
  const keys = (await readAllRecords())
    .filter((record) => record.accountId === id)
    .map((record) => record.key);
  await deleteRecords(keys);
}
