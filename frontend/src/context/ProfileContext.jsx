import { createContext, useContext, useState, useEffect } from 'react';

const ProfileContext = createContext();

export const useProfile = () => useContext(ProfileContext);

const DEFAULT_PROFILE = {
  learner_id: '',
  name: '',
  academic_level: 'class_11',
  exam_target: ['JEE'],
  learning_style: 'visual',
  pace_preference: 'balanced',
  weak_subjects: [],
  confidence_map: {
    Chemistry: 50,
    Physics: 50,
    Mathematics: 50
  },
  created_at: '',
  updated_at: ''
};

export const ProfileProvider = ({ children }) => {
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [loading, setLoading] = useState(true);

  // Load profile from API or LocalStorage fallback
  useEffect(() => {
    async function loadProfile() {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);
        const response = await fetch('/api/load/profile.json', {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          const data = await response.json();
          if (data && data.learner_id) {
            setProfile(data);
            return;
          }
        }
      } catch (err) {
        console.warn('Failed to load profile from server, checking local storage:', err);
      }

      // Check local storage fallback
      const local = localStorage.getItem('learnos_profile');
      if (local) {
        try {
          setProfile(JSON.parse(local));
        } catch { /* Optional persisted data may be absent. */ }
      } else {
        // Generate new guest profile
        const newProfile = {
          ...DEFAULT_PROFILE,
          learner_id: `user-${Math.random().toString(36).substr(2, 9)}`,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        setProfile(newProfile);
        localStorage.setItem('learnos_profile', JSON.stringify(newProfile));
      }
    }
    loadProfile().finally(() => setLoading(false));
  }, []);

  // Save profile to API and local storage
  const updateProfile = async (updates) => {
    const newProfile = {
      ...profile,
      ...updates,
      updated_at: new Date().toISOString()
    };

    setProfile(newProfile);
    localStorage.setItem('learnos_profile', JSON.stringify(newProfile));

    try {
      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'profile.json',
          payload: newProfile
        })
      });
    } catch (err) {
      console.error('Failed to sync profile with server:', err);
    }
  };

  const resetProfile = async () => {
    const newId = `user-${Math.random().toString(36).substr(2, 9)}`;
    const freshProfile = {
      ...DEFAULT_PROFILE,
      learner_id: newId,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    setProfile(freshProfile);
    localStorage.setItem('learnos_profile', JSON.stringify(freshProfile));

    try {
      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'profile.json',
          payload: freshProfile
        })
      });
      
      // Clear other files by writing empty targets
      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: 'history.json', payload: { sessions: [] } })
      });

      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'analytics.json',
          payload: {
            total_sessions: 0,
            total_watch_time_seconds: 0,
            topics_covered: [],
            weak_topic_flags: [],
            daily_activity: [],
            subject_distribution: {}
          }
        })
      });
    } catch (err) {
      console.error('Failed to reset data on server:', err);
    }
  };

  return (
    <ProfileContext.Provider value={{ profile, updateProfile, resetProfile, loading }}>
      {children}
    </ProfileContext.Provider>
  );
};
