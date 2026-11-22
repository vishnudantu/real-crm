"""HTTP exceptions raised by construction milestone operations."""

from fastapi import HTTPException, status


class ProjectNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Project not found.")


class MilestoneNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Construction milestone not found.")


class MilestoneSequenceAlreadyExistsError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            "This sequence number is already used in the project.",
        )


class MilestoneNotCompletedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "Only a COMPLETED milestone at 100 percent can be certified.",
        )
