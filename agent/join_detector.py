def detect_joins(schema):

    joins = []

    tables = list(schema.keys())

    for t1 in tables:
        for t2 in tables:

            if t1 == t2:
                continue

            cols1 = schema[t1]
            cols2 = schema[t2]

            cols1_names = [c["column"].lower() for c in cols1]
            cols2_names = [c["column"].lower() for c in cols2]

            common_cols = set(cols1_names).intersection(cols2_names)

            for col in common_cols:

                if col.endswith("_id"):

                    join = f"stg_{t1.lower()}.{col} = stg_{t2.lower()}.{col}"

                    joins.append(join)

    return list(set(joins))