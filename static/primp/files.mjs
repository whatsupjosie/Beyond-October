// Download requests have no completion signal. Only a successfully closed writer
// confirms the save. A cancelled picker never silently falls back to a download.
export async function saveLookFile(blobOrBuild, name, {picker, download}) {
  const build = () => typeof blobOrBuild === 'function' ? blobOrBuild() : blobOrBuild;
  if (!picker) {
    download(await build(), name);
    return {confirmed: false};
  }
  const handle = await picker({suggestedName: name, types: [{description: 'Primp editable look', accept: {'application/json': ['.primp']}}]});
  const blob = await build();
  const writer = await handle.createWritable();
  try {
    await writer.write(blob);
    await writer.close();
    return {confirmed: true};
  } catch (error) {
    try { await writer.abort(); } catch { /* Preserve the original write/close error. */ }
    throw error;
  }
}
