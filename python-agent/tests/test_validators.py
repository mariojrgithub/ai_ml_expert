"""Unit tests for app.validators — pure functions, no Docker required."""
from app.validators import validate_sql, validate_mongo, validate_code


# ---------------------------------------------------------------------------
# validate_sql
# ---------------------------------------------------------------------------

def test_validate_sql_clean_select_no_warnings():
    _, warnings = validate_sql("SELECT id, name FROM users WHERE active = 1 LIMIT 10")
    assert warnings == []


def test_validate_sql_warns_on_delete():
    _, warnings = validate_sql("DELETE FROM users WHERE id = 5")
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_sql_warns_on_update():
    _, warnings = validate_sql("UPDATE orders SET status='shipped' WHERE id = 3")
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_sql_warns_on_drop():
    _, warnings = validate_sql("DROP TABLE sessions")
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_sql_warns_on_insert():
    _, warnings = validate_sql("INSERT INTO users (name) VALUES ('bob')")
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_sql_warns_when_no_select():
    _, warnings = validate_sql("SHOW TABLES")
    assert any("SELECT" in w for w in warnings)


def test_validate_sql_returns_original_text_unchanged():
    sql = "SELECT * FROM sessions LIMIT 5"
    text, _ = validate_sql(sql)
    assert text == sql


# ---------------------------------------------------------------------------
# validate_mongo
# ---------------------------------------------------------------------------

def test_validate_mongo_clean_find_no_warnings():
    _, warnings = validate_mongo('db.users.find({ active: true }).limit(10)')
    assert warnings == []


def test_validate_mongo_warns_on_where():
    _, warnings = validate_mongo('db.orders.find({ $where: "this.x > 1" })')
    assert any("$where" in w for w in warnings)


def test_validate_mongo_warns_on_delete():
    _, warnings = validate_mongo('db.users.deleteMany({ inactive: true })')
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_mongo_warns_on_drop():
    _, warnings = validate_mongo('db.sessions.drop()')
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_mongo_warns_on_remove():
    _, warnings = validate_mongo('db.users.remove({})')
    assert any("destructive" in w.lower() for w in warnings)


def test_validate_mongo_returns_original_text_unchanged():
    query = 'db.items.find({ status: "active" })'
    text, _ = validate_mongo(query)
    assert text == query


# ---------------------------------------------------------------------------
# validate_code
# ---------------------------------------------------------------------------

def test_validate_code_python_with_function_no_warnings():
    code = "def add(a, b):\n    return a + b"
    _, warnings = validate_code(code, "python")
    assert warnings == []


def test_validate_code_python_with_class_no_warnings():
    code = "class MyService:\n    pass"
    _, warnings = validate_code(code, "python")
    assert warnings == []


def test_validate_code_python_warns_when_no_def_or_class():
    code = "x = 1 + 2\nprint(x)"
    _, warnings = validate_code(code, "python")
    assert any("incomplete" in w.lower() for w in warnings)


def test_validate_code_java_with_class_no_warnings():
    code = "public class Greeter {\n    public String greet() { return \"hi\"; }\n}"
    _, warnings = validate_code(code, "java")
    assert warnings == []


def test_validate_code_java_warns_when_no_class():
    code = "System.out.println(\"hello\");"
    _, warnings = validate_code(code, "java")
    assert any("incomplete" in w.lower() for w in warnings)


def test_validate_code_returns_original_text_unchanged():
    code = "def foo(): pass"
    text, _ = validate_code(code, "python")
    assert text == code


def test_validate_code_unknown_language_no_warnings():
    # Languages other than python/java should produce no warnings
    _, warnings = validate_code("SELECT 1", "sql")
    assert warnings == []
