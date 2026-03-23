import snowflake.connector


def read_staging_views(connection):

    conn = snowflake.connector.connect(**connection)
    cursor = conn.cursor()

    query = """
    SELECT table_name
    FROM AI_ETL_DB.INFORMATION_SCHEMA.VIEWS
    WHERE table_schema = 'RAW'
      AND table_name LIKE 'STG_%'
    """

    cursor.execute(query)

    rows = cursor.fetchall()

    views = [r[0].lower() for r in rows]

    print("\nStaging views discovered:\n")

    for v in views:
        print(v)

    cursor.close()
    conn.close()

    return views