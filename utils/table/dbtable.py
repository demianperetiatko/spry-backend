class DBTable:
    def __init__(self, query, columns):
        self.query = query
        self.columns = columns

    def fetch_dicts(self):
        result = []
        for row in self.query.all():
            row_dict = {}
            for col in self.columns:
                if len(col) == 2:
                    dict_key, attr_name = col
                    value = getattr(row, attr_name)
                elif len(col) == 3:
                    dict_key, attr_name, formatter = col
                    value = formatter(row)
                else:
                    raise ValueError("Invalid column format")
                row_dict[dict_key] = value
            result.append(row_dict)
        return {
            "total_count": self.query.count(),
            "data": result,
        }
