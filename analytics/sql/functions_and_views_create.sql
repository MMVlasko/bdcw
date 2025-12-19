CREATE OR REPLACE FUNCTION calculate_habit_consistency(p_habit_id BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    v_total_relevant_logs INTEGER;
    v_completed_logs INTEGER;
    v_consistency NUMERIC;
BEGIN
    SELECT
        COUNT(*) FILTER (WHERE status IN ('completed', 'failed')),
        COUNT(*) FILTER (WHERE status = 'completed')
    INTO v_total_relevant_logs, v_completed_logs
    FROM habit_logs
    WHERE habit_id = p_habit_id;

    IF v_total_relevant_logs > 0 AND v_completed_logs > 0 THEN
        v_consistency := (v_completed_logs::NUMERIC / v_total_relevant_logs) * 100.0;
    ELSE
        v_consistency := 0.0;
    END IF;

    RETURN v_consistency;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_goal_completion_percentage(p_goal_id BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    v_target_val NUMERIC;
    v_first_val NUMERIC;
    v_current_val NUMERIC;
    v_percentage NUMERIC;
BEGIN
    SELECT target_value INTO v_target_val
    FROM goals WHERE id = p_goal_id;

    SELECT current_value INTO v_current_val
    FROM goal_progresses
    WHERE goal_id = p_goal_id
    ORDER BY progress_date DESC
    LIMIT 1;

    SELECT current_value INTO v_first_val
    FROM goal_progresses
    WHERE goal_id = p_goal_id
    ORDER BY progress_date
    LIMIT 1;


    IF v_current_val IS NOT NULL THEN
        v_percentage := (v_target_val - v_first_val) / (v_target_val - v_current_val) * 100.0;
    ELSE
        v_percentage := 0.0;
    END IF;

    RETURN v_percentage;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_user_habits_consistency()
RETURNS TABLE(
    user_id BIGINT,
    avg_habit_consistency NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        h.user_id,
        AVG(calculate_habit_consistency(h.id)) as avg_habit_consistency
    FROM habits h
    GROUP BY h.user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW user_progress_analytics AS
SELECT
    u.id as id,
    u.username,
    u.created_at as user_joined,

    COUNT(DISTINCT g.id) as total_goals,
    COUNT(DISTINCT CASE WHEN g.is_completed THEN g.id END) as completed_goals,
    COUNT(DISTINCT CASE WHEN g.deadline < CURRENT_DATE AND NOT g.is_completed THEN g.id END) as overdue_goals,
    AVG(calculate_goal_completion_percentage(g.id)) as avg_goal_progress,

    COUNT(DISTINCT h.id) as total_habits,
    COUNT(DISTINCT CASE WHEN h.is_active THEN h.id END) as active_habits,
    COALESCE(uhc.avg_habit_consistency, 0) as avg_habit_consistency,

    COUNT(DISTINCT gc.challenge_id) as total_challenges_participated,
    COUNT(DISTINCT CASE WHEN c.end_date < CURRENT_DATE THEN c.id END) as completed_challenges,

    COUNT(DISTINCT s1.subscriber_id) as subscribers_count,
    COUNT(DISTINCT s2.subscribing_id) as subscribing_count

FROM users u
LEFT JOIN goals g ON g.user_id = u.id
LEFT JOIN habits h ON h.user_id = u.id
LEFT JOIN get_user_habits_consistency() uhc ON uhc.user_id = u.id
LEFT JOIN goal_challenges gc ON gc.goal_id = g.id
LEFT JOIN challenges c ON c.id = gc.challenge_id
LEFT JOIN subscriptions s1 ON s1.subscribing_id = u.id
LEFT JOIN subscriptions s2 ON s2.subscriber_id = u.id
WHERE u.is_public = true
GROUP BY u.id, u.username, u.created_at, uhc.avg_habit_consistency;




CREATE OR REPLACE FUNCTION count_challenge_participants(p_challenge_id BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT g.user_id)
        FROM goal_challenges gc
        JOIN goals g ON g.id = gc.goal_id
        WHERE gc.challenge_id = p_challenge_id
          AND g.is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION count_challenge_goals(p_challenge_id BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT gc.goal_id)
        FROM goal_challenges gc
        JOIN goals g ON g.id = gc.goal_id
        WHERE gc.challenge_id = p_challenge_id
          AND g.is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION avg_challenge_progress(p_challenge_id BIGINT)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT AVG(calculate_goal_completion_percentage(g.id))
        FROM goal_challenges gc
        JOIN goals g ON g.id = gc.goal_id
        WHERE gc.challenge_id = p_challenge_id
          AND g.is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION is_challenge_active(p_challenge_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    v_challenge_record challenges%ROWTYPE;
BEGIN
    SELECT * INTO v_challenge_record
    FROM challenges
    WHERE id = p_challenge_id;

    IF v_challenge_record IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN v_challenge_record.is_active
           AND CURRENT_DATE BETWEEN v_challenge_record.start_date AND v_challenge_record.end_date;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION days_remaining(p_challenge_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
    v_end_date DATE;
BEGIN
    SELECT end_date INTO v_end_date
    FROM challenges
    WHERE id = p_challenge_id;

    IF v_end_date IS NULL THEN
        RETURN 0;
    END IF;

    RETURN GREATEST(0, v_end_date - CURRENT_DATE);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION days_passed(p_challenge_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    SELECT start_date, end_date INTO v_start_date, v_end_date
    FROM challenges
    WHERE id = p_challenge_id;

    IF v_start_date IS NULL OR v_end_date IS NULL THEN
        RETURN 0;
    END IF;

    IF CURRENT_DATE < v_start_date THEN
        RETURN 0;

    ELSIF CURRENT_DATE > v_end_date THEN
        RETURN v_end_date - v_start_date + 1;

    ELSE
        RETURN CURRENT_DATE - v_start_date + 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION time_progress_percentage(p_challenge_id BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    v_total_days INTEGER;
    v_passed_days INTEGER;
BEGIN
    SELECT
        (end_date - start_date + 1),
        days_passed(p_challenge_id)
    INTO v_total_days, v_passed_days
    FROM challenges
    WHERE id = p_challenge_id;

    IF v_total_days > 0 THEN
        RETURN (v_passed_days::NUMERIC / v_total_days) * 100.0;
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
    c.start_date,
    c.end_date,
    c.is_active,

    count_challenge_participants(c.id) as participants_count,
    count_challenge_goals(c.id) as goals_count,
    COALESCE(avg_challenge_progress(c.id), 0) as avg_progress_percentage,

    days_passed(c.id) as days_passed,
    days_remaining(c.id) as days_remaining,
    time_progress_percentage(c.id) as time_progress_percent,

    CASE
        WHEN CURRENT_DATE < c.start_date THEN 'not_started'
        WHEN CURRENT_DATE > c.end_date THEN 'finished'
        WHEN is_challenge_active(c.id) THEN 'active'
        ELSE 'inactive'
    END as status,

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



CREATE OR REPLACE FUNCTION count_category_goals(p_category_id BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)
        FROM goals
        WHERE category_id = p_category_id
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION count_category_habits(p_category_id BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)
        FROM habits
        WHERE category_id = p_category_id
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION count_category_challenges(p_category_id BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT challenge_id)
        FROM challenge_categories
        WHERE category_id = p_category_id
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION count_category_users(p_category_id BIGINT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT user_id)
        FROM (
            SELECT user_id FROM goals WHERE category_id = p_category_id AND is_public = true
            UNION
            SELECT user_id FROM habits WHERE category_id = p_category_id AND is_public = true
        ) combined_users
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION avg_category_goal_progress(p_category_id BIGINT)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT AVG(calculate_goal_completion_percentage(id))
        FROM goals
        WHERE category_id = p_category_id
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION avg_category_habit_consistency(p_category_id BIGINT)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT AVG(calculate_habit_consistency(id))
        FROM habits
        WHERE category_id = p_category_id
          AND is_public = true
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_category_activity_score(p_category_id BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    v_goals_count INTEGER;
    v_habits_count INTEGER;
    v_challenges_count INTEGER;
    v_users_count INTEGER;
    v_total_score NUMERIC;
BEGIN
    SELECT
        count_category_goals(p_category_id),
        count_category_habits(p_category_id),
        count_category_challenges(p_category_id),
        count_category_users(p_category_id)
    INTO v_goals_count, v_habits_count, v_challenges_count, v_users_count;

    v_total_score :=
        (v_goals_count * 1.0) +
        (v_habits_count * 0.8) +
        (v_challenges_count * 1.5) +
        (v_users_count * 0.5);

    RETURN v_total_score;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE VIEW category_detailed_analytics AS
SELECT
    c.id,
    c.name,
    c.description,
    c.created_at,
    c.updated_at,

    count_category_goals(c.id) as total_goals,
    count_category_habits(c.id) as total_habits,
    count_category_challenges(c.id) as total_challenges,
    count_category_users(c.id) as unique_users,

    COALESCE(avg_category_goal_progress(c.id), 0) as avg_goal_progress_percentage,
    COALESCE(avg_category_habit_consistency(c.id), 0) as avg_habit_consistency_percentage,

    calculate_category_activity_score(c.id) as activity_score,

    ROW_NUMBER() OVER (ORDER BY calculate_category_activity_score(c.id) DESC) as popularity_rank,

    CASE
        WHEN count_category_users(c.id) > 0
        THEN count_category_goals(c.id)::NUMERIC / count_category_users(c.id)
        ELSE 0
    END as goals_per_user,

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