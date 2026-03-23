def build_schema_context(schema):

    context = ""

    for table, cols in schema.items():

        context += f"\nTable: stg_{table.lower()}\n"

        for col in cols:
            context += f"- {col['column']} ({col['type']})\n"

    return context