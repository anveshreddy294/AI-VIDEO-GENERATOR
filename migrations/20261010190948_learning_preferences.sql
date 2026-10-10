-- Additive preferences on the existing RLS-protected account row.
-- Incomplete legacy accounts keep {} and complete setup once. No mastery data changes.
BEGIN;
ALTER TABLE public.profiles ADD COLUMN learning_preferences jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_learning_preferences_shape CHECK (
    learning_preferences = '{}'::jsonb OR COALESCE((
        jsonb_typeof(learning_preferences) = 'object'
        AND learning_preferences ?& ARRAY['education_level','interested_domains','custom_interest','preferred_language','learning_goal','personalization_enabled']
        AND learning_preferences - ARRAY['education_level','interested_domains','custom_interest','preferred_language','learning_goal','personalization_enabled'] = '{}'::jsonb
        AND learning_preferences->>'education_level' IN ('Primary','Secondary','Undergraduate','Other')
        AND CASE WHEN jsonb_typeof(learning_preferences->'interested_domains') = 'array' THEN
            jsonb_array_length(learning_preferences->'interested_domains') BETWEEN 1 AND 12
            AND learning_preferences->'interested_domains' <@ '["Sports","Dance","Music","Gaming","Technology","Science","Nature and Animals","Art and Design","Movies and Animation","Business and Entrepreneurship","Fitness","Other"]'::jsonb
            ELSE false END
        AND jsonb_typeof(learning_preferences->'custom_interest') = 'string'
        AND length(learning_preferences->>'custom_interest') <= 80
        AND ((learning_preferences->'interested_domains' ? 'Other') = (length(trim(learning_preferences->>'custom_interest')) > 0))
        AND learning_preferences->>'preferred_language' = 'English'
        AND learning_preferences->>'learning_goal' IN ('','Exam preparation','Concept understanding','Revision','Skill development')
        AND jsonb_typeof(learning_preferences->'personalization_enabled') = 'boolean'
    ), false)
);
-- Existing profiles_owner_select and profiles_owner_update policies already bind id=auth.uid().
-- Preserve column-limited grants; in particular never grant UPDATE(role).
GRANT UPDATE (learning_preferences) ON public.profiles TO authenticated;
COMMIT;
