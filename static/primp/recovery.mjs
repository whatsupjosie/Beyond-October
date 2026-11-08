// Compare and replace inside ONE IndexedDB transaction, including across tabs.
function unpack(value) {
  if (value === undefined) return {revision: 0, document: undefined};
  if (value?.format === 'primp') return {revision: 0, document: value}; // v1 recovery records
  if (!Number.isSafeInteger(value?.revision) || value.revision < 1 || !value.document) throw new Error('Local recovery data is invalid. Save your open look to a file.');
  return value;
}

// Updated writers use a separate key so an old open tab cannot overwrite them.
function currentRecord(store, done) {
  const current = store.get('recovery-v2');
  current.onsuccess = () => {
    if (current.result !== undefined) done(current.result);
    else { const legacy = store.get('recovery'); legacy.onsuccess = () => done(legacy.result); }
  };
}

export function readRecoveryRecord(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('looks', 'readonly');
    let record, error;
    currentRecord(transaction.objectStore('looks'), value => { try { record = unpack(value); } catch (failure) { error = failure; transaction.abort(); } });
    transaction.oncomplete = () => resolve(record);
    transaction.onabort = () => reject(error || transaction.error || new Error('Recovery read was interrupted.'));
    transaction.onerror = () => reject(transaction.error || new Error('Recovery read failed.'));
  });
}

export function writeRecoveryRecord(db, document, expectedRevision) {
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0 || expectedRevision >= Number.MAX_SAFE_INTEGER) return Promise.reject(new Error('Invalid recovery revision.'));
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('looks', 'readwrite');
    const store = transaction.objectStore('looks');
    let error;
    currentRecord(store, value => {
      try {
        if (unpack(value).revision !== expectedRevision) throw new Error('Another tab saved a newer recovery look. Save your open look to a file, or recover the newer look before continuing.');
        store.put({revision: expectedRevision + 1, document}, 'recovery-v2');
      } catch (failure) { error = failure; transaction.abort(); }
    });
    transaction.oncomplete = () => resolve(expectedRevision + 1);
    transaction.onabort = () => reject(error || transaction.error || new Error('Recovery write was interrupted.'));
    transaction.onerror = () => reject(transaction.error || new Error('Recovery write failed.'));
  });
}
