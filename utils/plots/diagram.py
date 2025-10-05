from typing import Any
from typing import List
from typing import Tuple


class Diagram:
    def __init__(
        self,
        items: List[dict],
        metrics: List[Tuple[str, str, Any]],
    ):
        self.items = items
        self.metrics = metrics

    def as_dict(self) -> List:
        formatted_data = []

        for key, title, func in self.metrics:
            try:
                info = {
                    "key": key,
                    "title": title,
                    **func(self.items or []),
                }
            except Exception:
                info = {
                    "key": key,
                    "title": title,
                }
            formatted_data.append(info)

        return formatted_data
