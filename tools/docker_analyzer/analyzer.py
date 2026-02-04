"""Core Docker image analysis logic."""

import docker
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LayerInfo:
    """Information about a Docker image layer."""

    id: str
    size: int
    created_by: str
    comment: str = ""

    @property
    def size_mb(self) -> float:
        """Get size in megabytes."""
        return self.size / (1024 * 1024)

    @property
    def size_human(self) -> str:
        """Get human-readable size."""
        return format_bytes(self.size)


@dataclass
class ImageAnalysis:
    """Complete analysis of a Docker image."""

    name: str
    tags: List[str]
    id: str
    created: str
    size: int
    layers: List[LayerInfo]
    architecture: str
    os: str
    error: Optional[str] = None

    @property
    def size_mb(self) -> float:
        """Get size in megabytes."""
        return self.size / (1024 * 1024)

    @property
    def size_human(self) -> str:
        """Get human-readable size."""
        return format_bytes(self.size)

    @property
    def layer_count(self) -> int:
        """Get number of layers."""
        return len(self.layers)

    @property
    def largest_layers(self) -> List[LayerInfo]:
        """Get top 5 largest layers."""
        return sorted(self.layers, key=lambda l: l.size, reverse=True)[:5]


def format_bytes(bytes_val: int) -> str:
    """
    Format bytes into human-readable string.

    Args:
        bytes_val: Number of bytes

    Returns:
        Human-readable string (e.g., "1.5 GB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


class DockerAnalyzer:
    """
    Analyze Docker images for size and optimization opportunities.

    Attributes:
        client: Docker client instance
    """

    def __init__(self):
        """Initialize Docker analyzer."""
        try:
            self.client = docker.from_env()
            logger.debug("Connected to Docker daemon")
        except docker.errors.DockerException as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise ConnectionError(f"Cannot connect to Docker daemon: {e}")

    def analyze_image(self, image_name: str) -> ImageAnalysis:
        """
        Analyze a Docker image.

        Args:
            image_name: Image name or ID

        Returns:
            ImageAnalysis object
        """
        logger.info(f"Analyzing image: {image_name}")

        try:
            # Get image
            image = self.client.images.get(image_name)

            # Get basic info
            name = image_name
            tags = image.tags
            image_id = image.id
            created = image.attrs.get("Created", "Unknown")
            size = image.attrs.get("Size", 0)
            architecture = image.attrs.get("Architecture", "Unknown")
            os_info = image.attrs.get("Os", "Unknown")

            # Get layer information
            layers = self._extract_layers(image)

            return ImageAnalysis(
                name=name,
                tags=tags,
                id=image_id,
                created=created,
                size=size,
                layers=layers,
                architecture=architecture,
                os=os_info,
            )

        except docker.errors.ImageNotFound:
            logger.error(f"Image not found: {image_name}")
            return self._create_error_analysis(image_name, "Image not found")

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            return self._create_error_analysis(image_name, f"Docker API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error analyzing {image_name}: {e}")
            return self._create_error_analysis(image_name, f"Error: {e}")

    def _extract_layers(self, image) -> List[LayerInfo]:
        """
        Extract layer information from image.

        Args:
            image: Docker image object

        Returns:
            List of LayerInfo objects
        """
        layers = []

        # Get history (layers with commands)
        history = image.history()

        for entry in history:
            layer_id = entry.get("Id", "N/A")
            size = entry.get("Size", 0)
            created_by = entry.get("CreatedBy", "")
            comment = entry.get("Comment", "")

            # Clean up created_by command
            if created_by.startswith("/bin/sh -c"):
                created_by = created_by.replace("/bin/sh -c ", "RUN ", 1)
            if created_by.startswith("#(nop)"):
                created_by = created_by.replace("#(nop) ", "", 1)

            # Truncate long commands
            if len(created_by) > 100:
                created_by = created_by[:97] + "..."

            layer = LayerInfo(
                id=layer_id,
                size=size,
                created_by=created_by,
                comment=comment,
            )
            layers.append(layer)

        # Reverse to show oldest layer first
        return list(reversed(layers))

    def _create_error_analysis(self, image_name: str, error: str) -> ImageAnalysis:
        """
        Create ImageAnalysis for error cases.

        Args:
            image_name: Image name
            error: Error message

        Returns:
            ImageAnalysis with error
        """
        return ImageAnalysis(
            name=image_name,
            tags=[],
            id="N/A",
            created="N/A",
            size=0,
            layers=[],
            architecture="N/A",
            os="N/A",
            error=error,
        )

    def compare_images(self, image1: str, image2: str) -> Tuple[ImageAnalysis, ImageAnalysis]:
        """
        Compare two Docker images.

        Args:
            image1: First image name
            image2: Second image name

        Returns:
            Tuple of (ImageAnalysis1, ImageAnalysis2)
        """
        analysis1 = self.analyze_image(image1)
        analysis2 = self.analyze_image(image2)
        return (analysis1, analysis2)

    def list_images(self) -> List[dict]:
        """
        List all Docker images on the system.

        Returns:
            List of image information dicts
        """
        images = self.client.images.list()
        result = []

        for img in images:
            result.append(
                {
                    "id": img.id,
                    "tags": img.tags,
                    "size": img.attrs.get("Size", 0),
                    "size_human": format_bytes(img.attrs.get("Size", 0)),
                    "created": img.attrs.get("Created", "Unknown"),
                }
            )

        return result

    def get_optimization_suggestions(self, analysis: ImageAnalysis) -> List[str]:
        """
        Generate optimization suggestions based on analysis.

        Args:
            analysis: ImageAnalysis object

        Returns:
            List of suggestion strings
        """
        suggestions = []

        if analysis.error:
            return suggestions

        # Check for large image size
        if analysis.size_mb > 1000:
            suggestions.append(
                f"⚠️  Image is very large ({analysis.size_human}). Consider using a smaller base image (alpine, distroless)."
            )

        # Check for too many layers
        if analysis.layer_count > 50:
            suggestions.append(
                f"⚠️  Too many layers ({analysis.layer_count}). Combine RUN commands to reduce layer count."
            )

        # Check for largest layers
        large_layers = [l for l in analysis.layers if l.size_mb > 100]
        if large_layers:
            suggestions.append(
                f"⚠️  Found {len(large_layers)} layer(s) over 100 MB. Review largest layers for optimization opportunities."
            )

        # Check for apt cache cleanup
        apt_commands = [l for l in analysis.layers if "apt-get" in l.created_by.lower()]
        if apt_commands:
            has_cleanup = any(
                "rm -rf /var/lib/apt" in l.created_by.lower() for l in analysis.layers
            )
            if not has_cleanup:
                suggestions.append(
                    "💡 Detected apt-get usage without cache cleanup. Add: && rm -rf /var/lib/apt/lists/*"
                )

        # Check for package manager cache
        if any("npm install" in l.created_by for l in analysis.layers):
            has_npm_clean = any("npm cache clean" in l.created_by for l in analysis.layers)
            if not has_npm_clean:
                suggestions.append(
                    "💡 Detected npm install without cache cleanup. Add: && npm cache clean --force"
                )

        # General suggestions
        if not suggestions:
            suggestions.append("✅ Image looks reasonably optimized!")

        return suggestions

    def pull_image(self, image_name: str) -> bool:
        """
        Pull an image from Docker registry.

        Args:
            image_name: Image name to pull

        Returns:
            True if successful
        """
        try:
            logger.info(f"Pulling image: {image_name}")
            self.client.images.pull(image_name)
            logger.info(f"Successfully pulled {image_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull {image_name}: {e}")
            return False
