from ai_sql_agent_mcp.guardrails import validate_query


def test_allows_simple_select():
    result = validate_query("SELECT * FROM users")
    assert result.allowed is True
    assert "LIMIT 500" in result.sanitized_sql


def test_allows_with_cte():
    result = validate_query("WITH t AS (SELECT 1) SELECT * FROM t")
    assert result.allowed is True


def test_rejects_insert():
    result = validate_query("INSERT INTO users (name) VALUES ('x')")
    assert result.allowed is False
    assert "SELECT" in result.reason


def test_rejects_drop_table():
    result = validate_query("DROP TABLE users")
    assert result.allowed is False


def test_rejects_stacked_statements():
    result = validate_query("SELECT * FROM users; DROP TABLE users;")
    assert result.allowed is False
    assert "single" in result.reason.lower()


def test_trailing_line_comment_is_inert_and_allowed():
    # A trailing comment never executes as SQL, so text inside it (even a
    # forbidden keyword) does not make the *actual* statement unsafe.
    # This is correct behavior, not a bypass: nothing after '--' runs.
    result = validate_query("SELECT * FROM users; --DELETE FROM users")
    assert result.allowed is True


def test_block_comment_is_inert_and_allowed():
    result = validate_query("SELECT * FROM users /* also DROP TABLE users */")
    assert result.allowed is True


def test_rejects_keyword_split_across_block_comment():
    # Real attack vector: an attacker splits a forbidden keyword with an
    # empty block comment (DR/**/OP) hoping a naive substring scan misses
    # it. Because we strip comments *before* scanning, the tokens rejoin
    # into "DROP" and get caught.
    result = validate_query("DR/**/OP TABLE users")
    assert result.allowed is False


def test_does_not_false_positive_on_column_names():
    # 'created_at' contains 'CREATE' as a substring but must not trigger
    # the forbidden-keyword check (word-boundary matching).
    result = validate_query("SELECT created_at FROM users")
    assert result.allowed is True


def test_caps_oversized_limit():
    result = validate_query("SELECT * FROM users LIMIT 100000", max_rows=500)
    assert result.allowed is True
    assert "LIMIT 500" in result.sanitized_sql
    assert "100000" not in result.sanitized_sql


def test_preserves_limit_within_bounds():
    result = validate_query("SELECT * FROM users LIMIT 10", max_rows=500)
    assert result.allowed is True
    assert "LIMIT 10" in result.sanitized_sql


def test_rejects_empty_query():
    result = validate_query("")
    assert result.allowed is False


def test_rejects_update():
    result = validate_query("UPDATE users SET name = 'x' WHERE id = 1")
    assert result.allowed is False
