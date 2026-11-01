
export async function requestCameraFollow(userId, shot = 'medium', target = 'program') {
  const res = await fetch('/api/avatar-studio/camera/follow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, shot, target }),
  });
  if (!res.ok) throw new Error(`camera follow failed: ${res.status}`);
  return res.json();
}

export async function requestArchitectPlan(room, prompt, focusUserId = '') {
  const res = await fetch('/api/avatar-studio/architect/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ room, prompt, focus_user_id: focusUserId }),
  });
  if (!res.ok) throw new Error(`architect plan failed: ${res.status}`);
  return res.json();
}
