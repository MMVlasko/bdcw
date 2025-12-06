
-- 1. Функция для таблиц с обычными первичными ключами
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    has_id BOOLEAN;
    old_data JSONB;
    new_data JSONB;
    user_id BIGINT;
    record_id BIGINT;
BEGIN
    -- Получаем user_id из настроек сессии
    user_id := NULLIF(current_setting('app.user_id', TRUE), '')::BIGINT;
    has_id := EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = TG_TABLE_NAME
          AND column_name = 'id'
    );

    IF has_id THEN
        IF (TG_OP = 'INSERT' OR TG_OP = 'UPDATE') THEN
            -- Используем динамический SQL для безопасного доступа к NEW.id
            EXECUTE format('SELECT ($1).id')
            INTO record_id
            USING NEW;
        ELSIF (TG_OP = 'DELETE') THEN
            EXECUTE format('SELECT ($1).id')
            INTO record_id
            USING OLD;
        END IF;
    END IF;


    IF (TG_OP = 'INSERT') THEN
        old_data := NULL;
        new_data := to_jsonb(NEW);

        INSERT INTO audit_logs (
            table_name, record_id, operation,
            old_values, new_values, changed_by_id
        ) VALUES (
            TG_TABLE_NAME, record_id, 'INSERT',
            old_data, new_data, user_id
        );
        RETURN NEW;

    ELSIF (TG_OP = 'UPDATE') THEN
        old_data := to_jsonb(OLD);
        new_data := to_jsonb(NEW);

        IF (old_data != new_data) THEN
            INSERT INTO audit_logs (
            table_name, record_id, operation,
            old_values, new_values, changed_by_id
        ) VALUES (
            TG_TABLE_NAME, record_id, 'INSERT',
            old_data, new_data, user_id
        );
        END IF;
        RETURN NEW;

    ELSIF (TG_OP = 'DELETE') THEN
        old_data := to_jsonb(OLD);
        new_data := NULL;

        INSERT INTO audit_logs (
            table_name, record_id, operation,
            old_values, new_values, changed_by_id
        ) VALUES (
            TG_TABLE_NAME, record_id, 'INSERT',
            old_data, new_data, user_id
        );
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_users_trigger ON users CASCADE;
DROP TRIGGER IF EXISTS audit_goals_trigger ON goals CASCADE;
DROP TRIGGER IF EXISTS audit_habits_trigger ON habits CASCADE;
DROP TRIGGER IF EXISTS audit_auth_tokens_trigger ON auth_tokens CASCADE;
DROP TRIGGER IF EXISTS audit_categories_trigger ON categories CASCADE;
DROP TRIGGER IF EXISTS audit_habit_logs_trigger ON habit_logs CASCADE;
DROP TRIGGER IF EXISTS audit_goal_progresses_trigger ON goal_progresses CASCADE;
DROP TRIGGER IF EXISTS audit_challenges_trigger ON challenges CASCADE;
DROP TRIGGER IF EXISTS audit_subscriptions_trigger ON subscriptions CASCADE;
DROP TRIGGER IF EXISTS audit_goal_challenges_trigger ON goal_challenges CASCADE;
DROP TRIGGER IF EXISTS audit_challenge_categories_trigger ON challenge_categories CASCADE;

CREATE TRIGGER audit_users_trigger
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_goals_trigger
AFTER INSERT OR UPDATE OR DELETE ON goals
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_habits_trigger
AFTER INSERT OR UPDATE OR DELETE ON habits
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_auth_tokens_trigger
AFTER INSERT OR UPDATE OR DELETE ON auth_tokens
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_categories_trigger
AFTER INSERT OR UPDATE OR DELETE ON categories
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_habit_logs_trigger
AFTER INSERT OR UPDATE OR DELETE ON habit_logs
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_goal_progresses_trigger
AFTER INSERT OR UPDATE OR DELETE ON goal_progresses
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_challenges_trigger
AFTER INSERT OR UPDATE OR DELETE ON challenges
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_subscriptions_trigger
AFTER INSERT OR DELETE ON subscriptions
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_goal_challenges_trigger
AFTER INSERT OR DELETE ON goal_challenges
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_challenge_categories_trigger
AFTER INSERT OR DELETE ON challenge_categories
FOR EACH ROW
EXECUTE FUNCTION audit_trigger_function();