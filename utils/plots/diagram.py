from typing import Callable, Dict, List, Any, Tuple
from datetime import date


class Diagram:
    def __init__(
            self,
            items: List[dict],
            headers: List[Dict[str, Any]],
            metrics: List[Tuple[str, Callable[[List[dict]], Any]]],
    ):
        self.items = items
        self.headers = headers
        self.metrics = metrics

    def as_dict(self) -> Dict[str, Any]:
        formatted_data = {}

        for key, func in self.metrics:
            try:
                formatted_data[key] = func(self.items)
            except Exception:
                formatted_data[key] = None

        return {
            "data": formatted_data,
            "headers": self.headers
        }
