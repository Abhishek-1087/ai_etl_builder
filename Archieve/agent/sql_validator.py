FORBIDDEN = ["DROP", "DELETE", "TRUNCATE", "ALTER"]


def validate_sql(sql):

    upper_sql = sql.upper()

    for keyword in FORBIDDEN:

        if keyword in upper_sql:
            raise ValueError(f"Dangerous SQL detected: {keyword}")

    return True