from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.contracts.models import RiskItem
from vigilador_tecnologico.storage.service import StorageService


logger = logging.getLogger("vigilador_tecnologico.notifications")


@dataclass(slots=True)
class NotificationService:
    def notify_critical_risks(
        self,
        storage_service: StorageService,
        *,
        document_id: str,
        report_id: str,
        risks: list[RiskItem],
    ) -> list[dict[str, Any]]:
        notifications: list[dict[str, Any]] = []
        for risk in risks:
            severity = str(risk.get("severity") or "")
            if severity not in {"high", "critical"}:
                continue

            notification = {
                "notification_type": "critical_risk",
                "document_id": document_id,
                "report_id": report_id,
                "technology_name": risk["technology_name"],
                "severity": severity,
                "description": risk["description"],
                "source_urls": list(risk.get("source_urls", [])),
            }
            storage_service.audit.append("CriticalRiskAlert", document_id, notification)
            notifications.append(notification)
            logger.warning(
                "critical_risk_alert",
                extra={
                    "document_id": document_id,
                    "report_id": report_id,
                    "technology_name": risk["technology_name"],
                    "severity": severity,
                },
            )

        return notifications

    def notify_operation_failure(
        self,
        storage_service: StorageService,
        *,
        document_id: str,
        operation_id: str,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        notification = {
            "notification_type": "operation_failure",
            "document_id": document_id,
            "operation_id": operation_id,
            "error": error,
            "details": details or {},
        }
        storage_service.audit.append("OperationFailedAlert", document_id, notification)
        logger.error(
            "operation_failure_alert",
            extra={
                "document_id": document_id,
                "operation_id": operation_id,
                "error": error,
            },
        )
        return notification
