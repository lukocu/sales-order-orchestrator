from fastapi import HTTPException, status


def database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
    )
