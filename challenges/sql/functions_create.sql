CREATE OR REPLACE FUNCTION calculate_goal_progress(p_goal_id BIGINT)
RETURNS NUMERIC AS $$
DECLARE
    v_min_diff NUMERIC;
BEGIN
    SELECT MIN(ABS(gp.current_value - g.target_value))
    INTO v_min_diff
    FROM goal_progresses gp
    JOIN goals g ON g.id = gp.goal_id
    WHERE gp.goal_id = p_goal_id;

    RETURN v_min_diff;
END;
$$ LANGUAGE plpgsql;