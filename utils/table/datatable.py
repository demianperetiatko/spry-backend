class DataTable:
    def __init__(self, items, columns):
        self.items = items
        self.columns = columns

    def fetch_dicts(self, sort_by: str = None, sort_order: str = "asc"):
        result = []
        if sort_by:
            reverse = sort_order == "desc"
            try:
                self.items.sort(key=lambda x: x.get(sort_by), reverse=reverse)
            except Exception as e:
                raise ValueError(f"Sorting error: {e}")

        for row in self.items:
            row_dict = {}
            for col in self.columns:
                if len(col) == 2:
                    dict_key, attr_name = col
                    value = row.get(attr_name)
                elif len(col) == 3:
                    dict_key, attr_name, formatter = col
                    value = formatter(row)
                else:
                    raise ValueError("Invalid column format")
                row_dict[dict_key] = value
            result.append(row_dict)


        return {
            "total_count": len(result),
            "data": result,
        }
