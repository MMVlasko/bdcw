DROP TRIGGER IF EXISTS audit_users_trigger ON users;
DROP TRIGGER IF EXISTS audit_goals_trigger ON goals;
DROP TRIGGER IF EXISTS audit_habits_trigger ON habits;
DROP TRIGGER IF EXISTS audit_auth_tokens_trigger ON auth_tokens;
DROP TRIGGER IF EXISTS audit_categories_trigger ON categories;
DROP TRIGGER IF EXISTS audit_habit_logs_trigger ON habit_logs;
DROP TRIGGER IF EXISTS audit_goal_progresses_trigger ON goal_progresses;
DROP TRIGGER IF EXISTS audit_challenges_trigger ON challenges;
DROP TRIGGER IF EXISTS audit_subscriptions_trigger ON subscriptions;
DROP TRIGGER IF EXISTS audit_goal_challenges_trigger ON goal_challenges;
DROP TRIGGER IF EXISTS audit_challenge_categories_trigger ON challenge_categories;

DROP FUNCTION IF EXISTS audit_trigger_function CASCADE;
DROP FUNCTION IF EXISTS audit_composite_trigger_function CASCADE;