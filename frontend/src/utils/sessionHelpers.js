export function getSessionDate(session) {
  return session?.completed_at || session?.date || null;
}

export function formatSessionDate(session, locale = undefined) {
  const raw = getSessionDate(session);
  if (!raw) return '—';
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString(locale);
}

export function getSessionsThisWeek(sessions = []) {
  const weekAgo = new Date();
  weekAgo.setDate(weekAgo.getDate() - 7);
  weekAgo.setHours(0, 0, 0, 0);

  return sessions.filter((session) => {
    const raw = getSessionDate(session);
    if (!raw) return false;
    const parsed = new Date(raw);
    return !Number.isNaN(parsed.getTime()) && parsed >= weekAgo;
  }).length;
}

export function computeActiveStreak(dailyActivity = []) {
  const activeDates = new Set(
    dailyActivity.filter((entry) => entry.minutes > 0).map((entry) => entry.date)
  );
  if (!activeDates.size) return 0;

  let streak = 0;
  const cursor = new Date();
  cursor.setHours(0, 0, 0, 0);

  for (let i = 0; i < 365; i += 1) {
    const key = cursor.toISOString().split('T')[0];
    if (activeDates.has(key)) {
      streak += 1;
      cursor.setDate(cursor.getDate() - 1);
    } else {
      break;
    }
  }
  return streak;
}
