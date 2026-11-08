export async function verifiedRecoveryScope(auth = window.ReachAuth) {
  if (!auth) throw new Error('The shared session adapter is unavailable.');
  let response;
  try { response = await auth.nativeFetch('/api/auth/status'); }
  catch { throw new Error('The host session could not be checked. Local recovery is paused.'); }
  if (response.status === 404) return 'standalone';
  if (!response.ok) throw new Error('The host session could not be checked. Local recovery is paused.');
  const state = await response.json();
  if (state?.auth_enforced === false) return 'standalone';
  if (state?.auth_enforced !== true) throw new Error('The host session status is invalid. Local recovery is paused.');
  const verified = await auth.verify();
  if (!verified?.valid || !verified.username) throw new Error('Sign in to PubCast to use account-specific local recovery.');
  return `account:${verified.username}`;
}
