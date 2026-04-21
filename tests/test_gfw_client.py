"""Tests for src.data.gfw_client."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.data.gfw_client import GFWClient


class TestGFWClient:
    """GFWClient initialization and API calls."""

    def test_init_with_token(self) -> None:
        client = GFWClient(token="test_token")
        assert client.token == "test_token"
        assert "Authorization" in client.headers

    def test_test_connection_success(self) -> None:
        with patch("src.data.gfw_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp

            client = GFWClient(token="test_token")
            assert client.test_connection() is True

    def test_test_connection_unauthorized(self) -> None:
        with patch("src.data.gfw_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 401
            mock_get.return_value = mock_resp

            client = GFWClient(token="test_token")
            assert client.test_connection() is False

    def test_get_fishing_events(self) -> None:
        with patch("src.data.gfw_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"entries": [{"id": "1"}, {"id": "2"}]}
            mock_get.return_value = mock_resp

            client = GFWClient(token="test_token")
            events = client.get_indonesia_fishing_events("2023-01-01", "2023-12-31")
            assert events is not None
            assert len(events["entries"]) == 2

    def test_get_fishing_events_failure_returns_none(self) -> None:
        with patch("src.data.gfw_client.requests.get") as mock_get:
            mock_get.side_effect = Exception("Request failed")

            client = GFWClient(token="test_token")
            result = client.get_indonesia_fishing_events("2023-01-01", "2023-12-31")
            assert result is None

    def test_bulk_download(self, tmp_path) -> None:
        with patch("src.data.gfw_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"entries": [{"id": str(i)} for i in range(10)]}
            mock_get.return_value = mock_resp

            client = GFWClient(token="test_token")
            events = client.bulk_download_indonesia_data(year=2023)
            # 4 quarters × 10 entries
            assert len(events) == 40
