"""
Tests for the Detection-Preparation Pipeline - V4 Architecture.

Tests cover pipeline orchestration, configuration, and result handling.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.pipeline import (
    run_detection_preparation_cycle,
    run_full_pipeline,
    PipelineConfig,
    PipelineMode,
    PipelineResult,
)
from app.detection.engine import DetectedAlert, DetectionType, AlertSeverity


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def sample_alerts():
    """Create sample alerts for testing."""
    return [
        DetectedAlert(
            type=DetectionType.LATE_PAYMENT,
            severity=AlertSeverity.THIS_WEEK,
            entity_type="client",
            entity_id="client-123",
            entity_name="Acme Corp",
            details={"amount": 5000, "days_overdue": 14},
            detected_at=datetime.utcnow(),
        ),
        DetectedAlert(
            type=DetectionType.BUFFER_BREACH,
            severity=AlertSeverity.EMERGENCY,
            entity_type="system",
            entity_id="cash",
            entity_name="Cash Buffer",
            details={"shortfall": 2000},
            detected_at=datetime.utcnow(),
        ),
    ]


# =============================================================================
# Unit Tests - PipelineConfig
# =============================================================================

class TestPipelineConfig:
    """Tests for PipelineConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PipelineConfig()

        assert config.mode == PipelineMode.FULL
        assert config.detection_types is None
        assert config.skip_preparation is False
        assert config.max_alerts_to_prepare == 50
        assert config.include_low_severity is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = PipelineConfig(
            mode=PipelineMode.TARGETED,
            detection_types=["late_payment", "buffer_breach"],
            max_alerts_to_prepare=10,
            include_low_severity=False,
        )

        assert config.mode == PipelineMode.TARGETED
        assert len(config.detection_types) == 2
        assert config.max_alerts_to_prepare == 10


# =============================================================================
# Unit Tests - PipelineResult
# =============================================================================

class TestPipelineResult:
    """Tests for PipelineResult."""

    def test_result_creation(self):
        """Test result creation with default values."""
        result = PipelineResult(
            user_id="user-123",
            run_at=datetime.utcnow(),
            mode=PipelineMode.FULL,
        )

        assert result.alerts_detected == 0
        assert result.actions_prepared == 0
        assert result.errors == []

    def test_result_to_dict(self):
        """Test result serialization."""
        result = PipelineResult(
            user_id="user-123",
            run_at=datetime.utcnow(),
            mode=PipelineMode.FULL,
            alerts_detected=5,
            alerts_by_severity={"emergency": 1, "this_week": 4},
            actions_prepared=3,
            total_duration_ms=150,
        )

        result_dict = result.to_dict()

        assert result_dict["user_id"] == "user-123"
        assert result_dict["detection"]["alerts_detected"] == 5
        assert result_dict["preparation"]["actions_prepared"] == 3
        assert result_dict["performance"]["total_ms"] == 150


# =============================================================================
# Integration Tests - Pipeline Execution
# =============================================================================

class TestPipelineExecution:
    """Tests for pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_run(self, mock_db, sample_alerts):
        """Test running the full pipeline."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                # Setup detection mock
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                # Setup preparation mock
                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                assert result.alerts_detected == 2
                assert mock_detection.run_all_detections.called
                assert mock_preparation.prepare_actions_for_alerts.called

    @pytest.mark.asyncio
    async def test_critical_mode_only_runs_critical(self, mock_db, sample_alerts):
        """Test that critical mode only runs critical detections."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_critical_detections = AsyncMock(return_value=[sample_alerts[1]])
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                config = PipelineConfig(mode=PipelineMode.CRITICAL)

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                    config=config,
                )

                assert mock_detection.run_critical_detections.called
                assert result.alerts_detected == 1

    @pytest.mark.asyncio
    async def test_skip_preparation(self, mock_db, sample_alerts):
        """Test detection-only mode."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                MockPreparation.return_value = mock_preparation

                config = PipelineConfig(skip_preparation=True)

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                    config=config,
                )

                assert result.alerts_detected == 2
                assert result.actions_prepared == 0
                # Preparation should not be called
                assert not mock_preparation.prepare_actions_for_alerts.called

    @pytest.mark.asyncio
    async def test_max_alerts_limit(self, mock_db):
        """Test that max_alerts_to_prepare is respected."""
        # Create many alerts
        many_alerts = [
            DetectedAlert(
                type=DetectionType.LATE_PAYMENT,
                severity=AlertSeverity.UPCOMING,
                entity_type="client",
                entity_id=f"client-{i}",
                entity_name=f"Client {i}",
                details={},
                detected_at=datetime.utcnow(),
            )
            for i in range(100)
        ]

        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=many_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                config = PipelineConfig(max_alerts_to_prepare=10)

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                    config=config,
                )

                # Should prepare only first 10 alerts
                call_args = mock_preparation.prepare_actions_for_alerts.call_args
                assert len(call_args[0][0]) == 10

    @pytest.mark.asyncio
    async def test_exclude_low_severity(self, mock_db, sample_alerts):
        """Test filtering out low severity alerts."""
        # Add a low severity alert
        sample_alerts.append(
            DetectedAlert(
                type=DetectionType.REVENUE_VARIANCE,
                severity=AlertSeverity.UPCOMING,
                entity_type="metric",
                entity_id="revenue",
                entity_name="Revenue",
                details={},
                detected_at=datetime.utcnow(),
            )
        )

        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                config = PipelineConfig(include_low_severity=False)

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                    config=config,
                )

                # Should filter out UPCOMING alerts
                call_args = mock_preparation.prepare_actions_for_alerts.call_args
                filtered_alerts = call_args[0][0]
                assert all(a.severity.value != "upcoming" for a in filtered_alerts)


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_detection_error_captured(self, mock_db):
        """Test that detection errors are captured in result."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(
                    side_effect=Exception("Database error")
                )
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                assert len(result.errors) > 0
                assert "Detection error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_preparation_error_captured(self, mock_db, sample_alerts):
        """Test that preparation errors are captured in result."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(
                    side_effect=Exception("Preparation failed")
                )
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                assert len(result.errors) > 0
                assert "Preparation error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_pipeline_continues_on_non_fatal_error(self, mock_db, sample_alerts):
        """Test that pipeline continues even with errors."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(
                    side_effect=Exception("Linking failed")
                )
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                # Should still have detection results
                assert result.alerts_detected == 2
                # Error should be captured
                assert any("Linking error" in e for e in result.errors)


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformanceMetrics:
    """Tests for performance metric tracking."""

    @pytest.mark.asyncio
    async def test_duration_metrics_captured(self, mock_db, sample_alerts):
        """Test that duration metrics are captured."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                assert result.detection_duration_ms >= 0
                assert result.preparation_duration_ms >= 0
                assert result.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_alert_metrics_by_type(self, mock_db, sample_alerts):
        """Test that alerts are counted by type."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                assert "late_payment" in result.alerts_by_type
                assert "buffer_breach" in result.alerts_by_type

    @pytest.mark.asyncio
    async def test_alert_metrics_by_severity(self, mock_db, sample_alerts):
        """Test that alerts are counted by severity."""
        with patch('app.engines.pipeline.DetectionEngine') as MockDetection:
            with patch('app.engines.pipeline.PreparationEngine') as MockPreparation:
                mock_detection = AsyncMock()
                mock_detection.run_all_detections = AsyncMock(return_value=sample_alerts)
                MockDetection.return_value = mock_detection

                mock_preparation = AsyncMock()
                mock_preparation.prepare_actions_for_alerts = AsyncMock(return_value=[])
                mock_preparation._detect_linked_actions = AsyncMock(return_value=0)
                MockPreparation.return_value = mock_preparation

                result = await run_detection_preparation_cycle(
                    db=mock_db,
                    user_id="test-user",
                )

                assert "emergency" in result.alerts_by_severity
                assert "this_week" in result.alerts_by_severity
