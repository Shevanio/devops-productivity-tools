"""Tests for Docker Image Analyzer."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from tools.docker_analyzer.analyzer import DockerAnalyzer, ImageAnalysis, LayerInfo, format_bytes


class TestFormatBytes:
    """Test format_bytes utility."""

    def test_format_bytes(self):
        """Test bytes formatting."""
        assert "1.00 KB" in format_bytes(1024)
        assert "1.00 MB" in format_bytes(1024 * 1024)
        assert "1.00 GB" in format_bytes(1024 * 1024 * 1024)
        assert "500.00 B" in format_bytes(500)


class TestLayerInfo:
    """Test LayerInfo dataclass."""

    def test_layer_info_creation(self):
        """Test creating a LayerInfo."""
        layer = LayerInfo(
            id="sha256:abc123",
            size=1024 * 1024 * 50,  # 50 MB
            created_by="RUN apt-get update",
        )

        assert layer.id == "sha256:abc123"
        assert layer.size == 1024 * 1024 * 50
        assert layer.created_by == "RUN apt-get update"

    def test_layer_size_mb(self):
        """Test size_mb property."""
        layer = LayerInfo(id="test", size=1024 * 1024 * 100, created_by="test")
        assert layer.size_mb == pytest.approx(100.0, rel=0.1)

    def test_layer_size_human(self):
        """Test size_human property."""
        layer = LayerInfo(id="test", size=1024 * 1024 * 50, created_by="test")
        assert "MB" in layer.size_human


class TestImageAnalysis:
    """Test ImageAnalysis dataclass."""

    def test_image_analysis_creation(self):
        """Test creating an ImageAnalysis."""
        layers = [
            LayerInfo(id="1", size=100, created_by="FROM ubuntu"),
            LayerInfo(id="2", size=200, created_by="RUN apt-get update"),
        ]

        analysis = ImageAnalysis(
            name="test:latest",
            tags=["test:latest", "test:v1"],
            id="sha256:abc123",
            created="2024-01-01",
            size=1024 * 1024 * 500,  # 500 MB
            layers=layers,
            architecture="amd64",
            os="linux",
        )

        assert analysis.name == "test:latest"
        assert len(analysis.tags) == 2
        assert analysis.layer_count == 2

    def test_image_analysis_size_mb(self):
        """Test size_mb property."""
        analysis = ImageAnalysis(
            name="test",
            tags=[],
            id="test",
            created="test",
            size=1024 * 1024 * 250,
            layers=[],
            architecture="amd64",
            os="linux",
        )

        assert analysis.size_mb == pytest.approx(250.0, rel=0.1)

    def test_image_analysis_largest_layers(self):
        """Test largest_layers property."""
        layers = [
            LayerInfo(id="1", size=100, created_by="layer1"),
            LayerInfo(id="2", size=500, created_by="layer2"),
            LayerInfo(id="3", size=200, created_by="layer3"),
            LayerInfo(id="4", size=300, created_by="layer4"),
            LayerInfo(id="5", size=150, created_by="layer5"),
            LayerInfo(id="6", size=400, created_by="layer6"),
        ]

        analysis = ImageAnalysis(
            name="test",
            tags=[],
            id="test",
            created="test",
            size=1650,
            layers=layers,
            architecture="amd64",
            os="linux",
        )

        largest = analysis.largest_layers
        assert len(largest) == 5
        assert largest[0].size == 500  # Largest first
        assert largest[1].size == 400


class TestDockerAnalyzer:
    """Test DockerAnalyzer functionality."""

    def test_init_success(self):
        """Test successful initialization."""
        mock_client = MagicMock()

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            assert analyzer.client == mock_client

    def test_init_failure(self):
        """Test initialization failure when Docker is unavailable."""
        import docker

        with patch("docker.from_env", side_effect=docker.errors.DockerException("Not running")):
            with pytest.raises(ConnectionError, match="Cannot connect to Docker"):
                DockerAnalyzer()

    def test_analyze_image_not_found(self):
        """Test analyzing non-existent image."""
        import docker

        mock_client = MagicMock()
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            result = analyzer.analyze_image("nonexistent:latest")

        assert result.error == "Image not found"
        assert result.name == "nonexistent:latest"

    def test_analyze_image_success(self):
        """Test successful image analysis."""
        mock_client = MagicMock()

        # Mock image object
        mock_image = Mock()
        mock_image.id = "sha256:abc123def456"
        mock_image.tags = ["nginx:latest", "nginx:1.21"]
        mock_image.attrs = {
            "Created": "2024-01-01T00:00:00.000000000Z",
            "Size": 1024 * 1024 * 100,  # 100 MB
            "Architecture": "amd64",
            "Os": "linux",
        }
        mock_image.history.return_value = [
            {
                "Id": "sha256:layer1",
                "Size": 1024 * 1024 * 50,
                "CreatedBy": "/bin/sh -c apt-get update",
                "Comment": "",
            },
            {
                "Id": "sha256:layer2",
                "Size": 1024 * 1024 * 50,
                "CreatedBy": "#(nop) COPY file:abc /app",
                "Comment": "",
            },
        ]

        mock_client.images.get.return_value = mock_image

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            result = analyzer.analyze_image("nginx:latest")

        assert result.name == "nginx:latest"
        assert result.id == "sha256:abc123def456"
        assert len(result.tags) == 2
        assert result.size == 1024 * 1024 * 100
        assert len(result.layers) == 2
        assert result.error is None

    def test_extract_layers_command_cleanup(self):
        """Test that layer commands are cleaned up properly."""
        mock_client = MagicMock()
        mock_image = Mock()
        mock_image.id = "test"
        mock_image.tags = []
        mock_image.attrs = {
            "Created": "test",
            "Size": 100,
            "Architecture": "amd64",
            "Os": "linux",
        }
        mock_image.history.return_value = [
            {
                "Id": "test",
                "Size": 50,
                "CreatedBy": "/bin/sh -c apt-get install nginx",
                "Comment": "",
            },
            {
                "Id": "test2",
                "Size": 50,
                "CreatedBy": "#(nop) ENV PATH=/usr/local/bin",
                "Comment": "",
            },
        ]

        mock_client.images.get.return_value = mock_image

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            result = analyzer.analyze_image("test")

        # Check command cleanup
        assert "RUN apt-get install nginx" in result.layers[0].created_by
        assert "ENV PATH=/usr/local/bin" in result.layers[1].created_by
        assert "#(nop)" not in result.layers[1].created_by

    def test_compare_images(self):
        """Test comparing two images."""
        mock_client = MagicMock()

        def mock_get(image_name):
            mock_image = Mock()
            mock_image.id = f"sha256:{image_name}"
            mock_image.tags = [image_name]
            mock_image.attrs = {
                "Created": "2024-01-01",
                "Size": 1024 * 1024 * (100 if "v1" in image_name else 80),
                "Architecture": "amd64",
                "Os": "linux",
            }
            mock_image.history.return_value = []
            return mock_image

        mock_client.images.get.side_effect = mock_get

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            result1, result2 = analyzer.compare_images("myapp:v1", "myapp:v2")

        assert result1.name == "myapp:v1"
        assert result2.name == "myapp:v2"
        assert result1.size > result2.size  # v1 is larger

    def test_list_images(self):
        """Test listing all images."""
        mock_client = MagicMock()

        mock_img1 = Mock()
        mock_img1.id = "sha256:abc"
        mock_img1.tags = ["nginx:latest"]
        mock_img1.attrs = {"Size": 1024 * 1024 * 100, "Created": "2024-01-01"}

        mock_img2 = Mock()
        mock_img2.id = "sha256:def"
        mock_img2.tags = ["ubuntu:22.04"]
        mock_img2.attrs = {"Size": 1024 * 1024 * 80, "Created": "2024-01-02"}

        mock_client.images.list.return_value = [mock_img1, mock_img2]

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            images = analyzer.list_images()

        assert len(images) == 2
        assert images[0]["id"] == "sha256:abc"
        assert images[1]["id"] == "sha256:def"

    def test_get_optimization_suggestions_large_image(self):
        """Test suggestions for large image."""
        analysis = ImageAnalysis(
            name="test",
            tags=[],
            id="test",
            created="test",
            size=1024 * 1024 * 1024 * 2,  # 2 GB
            layers=[LayerInfo(id="1", size=100, created_by="test")],
            architecture="amd64",
            os="linux",
        )

        mock_client = MagicMock()
        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            suggestions = analyzer.get_optimization_suggestions(analysis)

        assert any("very large" in s.lower() for s in suggestions)

    def test_get_optimization_suggestions_many_layers(self):
        """Test suggestions for too many layers."""
        layers = [LayerInfo(id=str(i), size=100, created_by="test") for i in range(60)]

        analysis = ImageAnalysis(
            name="test",
            tags=[],
            id="test",
            created="test",
            size=6000,
            layers=layers,
            architecture="amd64",
            os="linux",
        )

        mock_client = MagicMock()
        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            suggestions = analyzer.get_optimization_suggestions(analysis)

        assert any("too many layers" in s.lower() for s in suggestions)

    def test_get_optimization_suggestions_apt_no_cleanup(self):
        """Test suggestions for apt without cleanup."""
        layers = [
            LayerInfo(id="1", size=100, created_by="RUN apt-get update && apt-get install nginx"),
        ]

        analysis = ImageAnalysis(
            name="test",
            tags=[],
            id="test",
            created="test",
            size=100,
            layers=layers,
            architecture="amd64",
            os="linux",
        )

        mock_client = MagicMock()
        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            suggestions = analyzer.get_optimization_suggestions(analysis)

        assert any("apt" in s.lower() and "cache cleanup" in s.lower() for s in suggestions)

    def test_pull_image_success(self):
        """Test successful image pull."""
        mock_client = MagicMock()
        mock_client.images.pull.return_value = Mock()

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            result = analyzer.pull_image("nginx:latest")

        assert result is True
        mock_client.images.pull.assert_called_once_with("nginx:latest")

    def test_pull_image_failure(self):
        """Test failed image pull."""
        mock_client = MagicMock()
        mock_client.images.pull.side_effect = Exception("Network error")

        with patch("docker.from_env", return_value=mock_client):
            analyzer = DockerAnalyzer()
            result = analyzer.pull_image("invalid:latest")

        assert result is False
