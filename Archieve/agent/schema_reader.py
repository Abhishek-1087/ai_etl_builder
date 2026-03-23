# import snowflake.connector


# def get_table_schema(table_name):

    # conn = snowflake.connector.connect(
    #     user="Abhishek",
    #     password="Sonu@1234567890",
    #     account="SREVWOM-EUB49120",
    #     warehouse="COMPUTE_WH",
    #     database="AI_ETL_DB",
    #     schema="RAW",
    #     role="ACCOUNTADMIN"
    # )

#     cursor = conn.cursor()

#     query = f"""
#     SELECT column_name, data_type
#     FROM information_schema.columns
#     WHERE table_name = '{table_name.upper()}'
#     """

#     cursor.execute(query)

#     columns = cursor.fetchall()

#     cursor.close()
#     conn.close()

#     return columns




import snowflake.connector


def read_schema(connection_params):

    conn = snowflake.connector.connect(**connection_params)
    cursor = conn.cursor()

    query = """
    SELECT
        table_name,
        column_name,
        data_type
    FROM SOURCE.INFORMATION_SCHEMA.COLUMNS
    WHERE table_schema = 'AI_RAW'
    ORDER BY table_name, ordinal_position
    """

    cursor.execute(query)

    rows = cursor.fetchall()

    print(f"\nTotal columns fetched: {len(rows)}")

    schema = {}

    for table, column, dtype in rows:

        table = table.upper()

        if table not in schema:
            schema[table] = []

        schema[table].append({
            "column": column,
            "type": dtype
        })

    cursor.close()
    conn.close()

    return schema