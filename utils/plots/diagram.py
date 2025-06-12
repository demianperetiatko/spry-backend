from typing import Callable, Dict, List, Any, Tuple
from datetime import date


class Diagram:
    def __init__(
            self,
            items: List[dict],
            metrics: List[Tuple[str, str, Callable[[List[dict]], Any]]],
    ):
        self.items = items
        self.metrics = metrics

    def as_dict(self) -> Dict[str, Any]:
        formatted_data = []

        for key, title, func in self.metrics:
            try:
                info = {
                    "key": key,
                    "title": title,
                    **func(self.items),
                }
                formatted_data.append(info)
            except Exception:
                pass

        return {
            "data": formatted_data,
        }
