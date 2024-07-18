from fastapi import APIRouter

router = APIRouter()


@router.get("/team/")
def team():
    return {"data": [
        ['Date', 'Recurring', 'One-time'],
        ['Jun 19', 70, 30],
        ['Jun 20', 80, 20],
        ['Jun 21', 50, 20],
        ['Jul 16', 40, 60],
        ['Jul 18', 40, 10],
        ['Jul 19', 40, 30],
        ['Jul 24', 40, 60]
    ]}
