"""Safe HTTP errors for approval lifecycle violations."""

from fastapi import HTTPException, status


class ApprovalRequestNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Approval request not found.")


class ApprovalRequestNotPendingError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, "Only a pending request can be changed.")


class SelfApprovalError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "You cannot approve your own request.")


class ApprovalCancellationForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "Only the requester or an admin can cancel.")


class ApprovalDecisionForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "Only a manager can decide an approval.")


class ApprovalApproverNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Approver not found.")


class ApprovalReferenceMissingError(HTTPException):
    """The referenced entity does not exist (or belongs to another tenant)."""

    def __init__(self, reference_type: str) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            f"The referenced {reference_type} no longer exists; the decision was not applied.",
        )


class ApprovalAmountInvalidError(HTTPException):
    """A DISCOUNT request must carry a strictly positive amount."""

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "A discount approval requires a positive amount_paise.",
        )
