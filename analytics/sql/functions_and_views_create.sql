CREATE OR REPLACE FUNCTION calculate_habit_consistency(habit_id_param BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    total_relevant_logs INTEGER;
    completed_logs INTEGER;
    consistency NUMERIC;
BEGIN
    -- Считаем только логи со статусами completed и failed
    -- skipped не учитываем вообще
    SELECT
        COUNT(*) FILTER (WHERE status IN ('completed', 'failed')),
        COUNT(*) FILTER (WHERE status = 'completed')
    INTO total_relevant_logs, completed_logs
    FROM habit_logs
    WHERE habit_id = habit_id_param;

    -- Рассчитываем процент completed от (completed + failed)
    IF total_relevant_logs > 0 THEN
        consistency := (completed_logs::NUMERIC / total_relevant_logs) * 100.0;
    ELSE
        consistency := 0.0; -- Нет записей со статусами
    END IF;

    RETURN consistency;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_goal_completion_percentage(p_goal_id BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    target_val NUMERIC;
    current_val NUMERIC;
    percentage NUMERIC;
BEGIN
    -- Получаем целевое значение
    SELECT target_value INTO target_val
    FROM goals WHERE id = p_goal_id;

    -- Получаем последнее текущее значение
    SELECT current_value INTO current_val
    FROM goal_progresses
    WHERE goal_id = p_goal_id
    ORDER BY progress_date DESC
    LIMIT 1;

    -- Рассчитываем процент
    IF target_val > 0 AND current_val IS NOT NULL THEN
        percentage := LEAST(100.0, (current_val / target_val) * 100.0);
    ELSE
        percentage := 0.0;
    END IF;

    RETURN percentage;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE VIEW user_progress_analytics AS
WITH user_habits_consistency AS (
    -- Вычисляем консистентность для каждой привычки пользователя
    SELECT
        h.user_id,
        AVG(calculate_habit_consistency(h.id)) as avg_habit_consistency
    FROM habits h
    WHERE EXISTS (
        SELECT 1 FROM habit_logs hl
        WHERE hl.habit_id = h.id
        AND hl.status IN ('completed', 'failed')
    )
    GROUP BY h.user_id
)
SELECT
    u.id as id,
    u.username,
    u.created_at as user_joined,

    -- Статистика по целям
    COUNT(DISTINCT g.id) as total_goals,
    COUNT(DISTINCT CASE WHEN g.is_completed THEN g.id END) as completed_goals,
    COUNT(DISTINCT CASE WHEN g.deadline < CURRENT_DATE AND NOT g.is_completed THEN g.id END) as overdue_goals,
    AVG(calculate_goal_completion_percentage(g.id)) as avg_goal_progress,

    -- Статистика по привычкам
    COUNT(DISTINCT h.id) as total_habits,
    COUNT(DISTINCT CASE WHEN h.is_active THEN h.id END) as active_habits,
    COALESCE(uhc.avg_habit_consistency, 0) as avg_habit_consistency,

    -- Статистика по челленджам
    COUNT(DISTINCT gc.challenge_id) as total_challenges_participated,
    COUNT(DISTINCT CASE WHEN c.end_date < CURRENT_DATE THEN c.id END) as completed_challenges,

    -- Социальная статистика
    COUNT(DISTINCT s1.subscriber_id) as subscribers_count,
    COUNT(DISTINCT s2.subscribing_id) as subscribing_count

FROM users u
LEFT JOIN goals g ON g.user_id = u.id
LEFT JOIN habits h ON h.user_id = u.id
LEFT JOIN user_habits_consistency uhc ON uhc.user_id = u.id
LEFT JOIN goal_challenges gc ON gc.goal_id = g.id
LEFT JOIN challenges c ON c.id = gc.challenge_id
LEFT JOIN subscriptions s1 ON s1.subscribing_id = u.id
LEFT JOIN subscriptions s2 ON s2.subscriber_id = u.id
WHERE u.is_public = true
GROUP BY u.id, u.username, u.created_at, uhc.avg_habit_consistency;




-- ----------------------------------

-- Функция для подсчета участников челленджа
CREATE OR REPLACE FUNCTION count_challenge_participants(challenge_id_param BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT g.user_id)
        FROM goal_challenges gc
        JOIN goals g ON g.id = gc.goal_id
        WHERE gc.challenge_id = challenge_id_param
          AND g.is_public = true
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для подсчета целей в челлендже
CREATE OR REPLACE FUNCTION count_challenge_goals(challenge_id_param BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT gc.goal_id)
        FROM goal_challenges gc
        JOIN goals g ON g.id = gc.goal_id
        WHERE gc.challenge_id = challenge_id_param
          AND g.is_public = true
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета среднего прогресса целей в челлендже
CREATE OR REPLACE FUNCTION avg_challenge_progress(challenge_id_param BIGINT)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT AVG(calculate_goal_completion_percentage(g.id))
        FROM goal_challenges gc
        JOIN goals g ON g.id = gc.goal_id
        WHERE gc.challenge_id = challenge_id_param
          AND g.is_public = true
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для проверки активности челленджа
CREATE OR REPLACE FUNCTION is_challenge_active(challenge_id_param BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    challenge_record challenges%ROWTYPE;
BEGIN
    SELECT * INTO challenge_record
    FROM challenges
    WHERE id = challenge_id_param;

    IF challenge_record IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN challenge_record.is_active
           AND CURRENT_DATE BETWEEN challenge_record.start_date AND challenge_record.end_date;
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета оставшихся дней
CREATE OR REPLACE FUNCTION days_remaining(challenge_id_param BIGINT)
RETURNS INTEGER AS $$
DECLARE
    end_date_val DATE;
BEGIN
    SELECT end_date INTO end_date_val
    FROM challenges
    WHERE id = challenge_id_param;

    IF end_date_val IS NULL THEN
        RETURN 0;
    END IF;

    RETURN GREATEST(0, end_date_val - CURRENT_DATE);
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета прошедших дней
CREATE OR REPLACE FUNCTION days_passed(challenge_id_param BIGINT)
RETURNS INTEGER AS $$
DECLARE
    start_date_val DATE;
    end_date_val DATE;
BEGIN
    SELECT start_date, end_date INTO start_date_val, end_date_val
    FROM challenges
    WHERE id = challenge_id_param;

    IF start_date_val IS NULL OR end_date_val IS NULL THEN
        RETURN 0;
    END IF;

    -- Если челлендж еще не начался
    IF CURRENT_DATE < start_date_val THEN
        RETURN 0;
    -- Если челлендж закончился
    ELSIF CURRENT_DATE > end_date_val THEN
        RETURN end_date_val - start_date_val + 1;
    -- Челендж в процессе
    ELSE
        RETURN CURRENT_DATE - start_date_val + 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета процента прошедшего времени
CREATE OR REPLACE FUNCTION time_progress_percentage(challenge_id_param BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    total_days INTEGER;
    passed_days INTEGER;
BEGIN
    SELECT
        (end_date - start_date + 1),
        days_passed(challenge_id_param)
    INTO total_days, passed_days
    FROM challenges
    WHERE id = challenge_id_param;

    IF total_days > 0 THEN
        RETURN (passed_days::NUMERIC / total_days) * 100.0;
    ELSE
        RETURN 0.0;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW challenge_basic_analytics AS
SELECT
    c.id,
    c.name,
    c.description,
    c.target_value,
    c.start_date,
    c.end_date,
    c.is_active,

    -- Базовые показатели из функций
    count_challenge_participants(c.id) as participants_count,
    count_challenge_goals(c.id) as goals_count,
    COALESCE(avg_challenge_progress(c.id), 0) as avg_progress_percentage,

    -- Показатели времени
    days_passed(c.id) as days_passed,
    days_remaining(c.id) as days_remaining,
    time_progress_percentage(c.id) as time_progress_percent,

    -- Статус челленджа
    CASE
        WHEN CURRENT_DATE < c.start_date THEN 'not_started'
        WHEN CURRENT_DATE > c.end_date THEN 'finished'
        WHEN is_challenge_active(c.id) THEN 'active'
        ELSE 'inactive'
    END as status,

    -- Плотность участия (целей на участника)
    CASE
        WHEN count_challenge_participants(c.id) > 0
        THEN count_challenge_goals(c.id)::NUMERIC / count_challenge_participants(c.id)
        ELSE 0
    END as goals_per_participant,

    (
        SELECT COUNT(*)
        FROM challenge_categories cc
        WHERE cc.challenge_id = c.id
    ) as categories_count

FROM challenges c
ORDER BY c.start_date DESC, c.name;



-- ------------------------------------------


-- Функция для подсчета целей в категории
CREATE OR REPLACE FUNCTION count_category_goals(category_id_param BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)
        FROM goals
        WHERE category_id = category_id_param
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для подсчета привычек в категории
CREATE OR REPLACE FUNCTION count_category_habits(category_id_param BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)
        FROM habits
        WHERE category_id = category_id_param
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для подсчета челленджей с категорией
CREATE OR REPLACE FUNCTION count_category_challenges(category_id_param BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT challenge_id)
        FROM challenge_categories
        WHERE category_id = category_id_param
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для подсчета уникальных пользователей в категории
CREATE OR REPLACE FUNCTION count_category_users(category_id_param BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT user_id)
        FROM (
            SELECT user_id FROM goals WHERE category_id = category_id_param AND is_public = true
            UNION
            SELECT user_id FROM habits WHERE category_id = category_id_param AND is_public = true
        ) combined_users
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета среднего прогресса целей в категории
CREATE OR REPLACE FUNCTION avg_category_goal_progress(category_id_param BIGINT)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT AVG(calculate_goal_completion_percentage(id))
        FROM goals
        WHERE category_id = category_id_param
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета средней консистентности привычек в категории
CREATE OR REPLACE FUNCTION avg_category_habit_consistency(category_id_param BIGINT)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT AVG(calculate_habit_consistency(id))
        FROM habits
        WHERE category_id = category_id_param
          AND is_public = true
          AND EXISTS (
              SELECT 1 FROM habit_logs hl
              WHERE hl.habit_id = habits.id
              AND hl.status IN ('completed', 'failed')
          )
    );
END;
$$ LANGUAGE plpgsql;

-- Функция для расчета общей активности в категории
CREATE OR REPLACE FUNCTION calculate_category_activity_score(category_id_param BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    goals_count INTEGER;
    habits_count INTEGER;
    challenges_count INTEGER;
    users_count INTEGER;
    total_score NUMERIC;
BEGIN
    SELECT
        count_category_goals(category_id_param),
        count_category_habits(category_id_param),
        count_category_challenges(category_id_param),
        count_category_users(category_id_param)
    INTO goals_count, habits_count, challenges_count, users_count;

    -- Взвешенная формула активности
    total_score :=
        (goals_count * 1.0) +
        (habits_count * 0.8) +
        (challenges_count * 1.5) +
        (users_count * 0.5);

    RETURN total_score;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE VIEW category_detailed_analytics AS
SELECT
    c.id,
    c.name,
    c.description,
    c.created_at,
    c.updated_at,

    -- Основные счетчики через функции
    count_category_goals(c.id) as total_goals,
    count_category_habits(c.id) as total_habits,
    count_category_challenges(c.id) as total_challenges,
    count_category_users(c.id) as unique_users,

    -- Статистика прогресса
    COALESCE(avg_category_goal_progress(c.id), 0) as avg_goal_progress_percentage,
    COALESCE(avg_category_habit_consistency(c.id), 0) as avg_habit_consistency_percentage,

    -- Активность
    calculate_category_activity_score(c.id) as activity_score,

    -- Рейтинг популярности (по активности)
    ROW_NUMBER() OVER (ORDER BY calculate_category_activity_score(c.id) DESC) as popularity_rank,

    -- Плотность (целей на пользователя)
    CASE
        WHEN count_category_users(c.id) > 0
        THEN count_category_goals(c.id)::NUMERIC / count_category_users(c.id)
        ELSE 0
    END as goals_per_user,

    -- Процент завершенных целей
    (
        SELECT
            CASE
                WHEN COUNT(*) > 0
                THEN COUNT(*) FILTER (WHERE is_completed = true)::NUMERIC / COUNT(*) * 100
                ELSE 0
            END
        FROM goals
        WHERE category_id = c.id
          AND is_public = true
    ) as goals_completion_rate,

    -- Процент активных привычек
    (
        SELECT
            CASE
                WHEN COUNT(*) > 0
                THEN COUNT(*) FILTER (WHERE is_active = true)::NUMERIC / COUNT(*) * 100
                ELSE 0
            END
        FROM habits
        WHERE category_id = c.id
          AND is_public = true
    ) as habits_activity_rate,

    -- Последняя активность
    (
        SELECT GREATEST(
            (SELECT MAX(created_at) FROM goals WHERE category_id = c.id AND is_public = true),
            (SELECT MAX(created_at) FROM habits WHERE category_id = c.id AND is_public = true),
            (SELECT MAX(joined_at) FROM goal_challenges gc
             JOIN goals g ON g.id = gc.goal_id
             WHERE g.category_id = c.id AND g.is_public = true)
        )
    ) as last_activity_date

FROM categories c
ORDER BY activity_score DESC, c.name;