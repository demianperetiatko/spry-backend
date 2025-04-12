from typing import Callable, Dict, List, Any, Tuple
from datetime import date


class Chart:
    def __init__(
        self,
        items: Dict[date, List[dict]],
        metrics: List[Tuple[str, Callable[[List[dict]], Any]]],
    ):
        self.items = items
        self.metrics = metrics

    def as_dict(self) -> Dict[str, Any]:
        formatted_data = []

        for day, events in self.items.items():
            row = {
                self.x_axis: day.strftime("%Y-%m-%d")
            }
            for key, func in self.metrics:
                try:
                    row[key] = func(events)
                except Exception:
                    row[key] = None
            formatted_data.append(row)

        return {
            "data": formatted_data,
        }
