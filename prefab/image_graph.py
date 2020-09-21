import json
from typing import Any, Callable, Dict, List, Tuple

from . import errors as E
from .config import Config
from .image import Image
from .logger import logger


class ImageGraph:
    def __init__(self, config: Config, image_factory: Callable) -> None:
        self.config: Config = config
        self.image_factory: Callable = image_factory
        self.images: Dict[str, Image] = {}
        self.targets: Dict[str, List[Image]] = {}

    def configure_target_image(self, target: str) -> Image:
        if target not in self.images:
            image = self.images[target] = self.image_factory(target)
            image.logger.info(f"target_image {image.name}")

        return self.images[target]

    def _resolve_target_images(
        self, target: str, images: List[Image], vectors: List[Tuple[str, str]]
    ) -> List[Image]:
        # use a depth-first search to unroll dependencies and detect loops.
        # targets have a directed dependency stream. if an upstream target
        # dependency changes, downstream dependencies also change, forcing
        # a new image build.
        for dependent in self.config.get_target(target).get("depends_on", []):
            vector = (target, dependent)
            if vector in vectors:
                raise E.TargetCyclicError(
                    f"Target [{target}] has circular dependencies"
                )
            else:
                checkpoint = len(vectors)
                vectors.append(vector)
                self._resolve_target_images(dependent, images, vectors)
                del vectors[checkpoint:]

        image = self.configure_target_image(target)
        if image not in images:
            images.append(image)

        return images

    def resolve_target_images(self, target: str) -> List[Image]:
        return self._resolve_target_images(target=target, images=[], vectors=[])

    @property
    def allowed_pull_errors(self) -> Tuple[Any, ...]:
        allowed_error_names = self.config.allowed_pull_errors
        return tuple(getattr(E, name) for name in dir(E) if name in allowed_error_names)

    def pull_target_image(self, image: Image) -> None:
        try:
            image.logger.info(f"{image.name} Trying pull...")
            image.pull()
        except Exception as error:
            if not isinstance(error, self.allowed_pull_errors):
                raise
            else:
                error_name = type(error).__name__
                image.logger.info(f"{image.name} {error_name}: {error}")
                image.logger.info(
                    f"{image.name} {error_name} in allowed_pull_errors, continuing..."
                )

    def load_target_image(self, image: Image) -> bool:
        if image.loaded:
            image.logger.info(f"{image.name} Image loaded")
        else:
            image.logger.info(f"{image.name} Image not loaded")
            self.pull_target_image(image)

        if image.loaded and self.config.validate_image:
            image.validate()
            image.logger.info(f"{image.name} Image validated")

        return image.loaded

    @staticmethod
    def display_image_build_options(image: Image) -> None:
        json_text = json.dumps(image.build_options, sort_keys=True, indent=4)
        json_lines = json_text.splitlines()
        image.logger.info(f"{image.name} build_options {json_lines.pop(0)}")

        for line in json_lines:
            image.logger.info(line)

    def should_load_target_image(self, target: str) -> bool:
        # only load images if no upstream dependencies were (re)built
        return not any(image for image in self.targets[target] if image.was_built)

    def _build_cleanup(self, image: Image) -> None:
        if self.config.prune_after_build:
            image.prune()

    def build_target_image(self, target: str) -> None:
        for image in self.targets[target]:
            if self.should_load_target_image(target):
                self.load_target_image(image)

            if not image.loaded:
                image.logger.info(f"{image.name} Trying build...")
                self.display_image_build_options(image)
                image.build()
                self._build_cleanup(image)

    def build(self, targets: List[str]) -> None:
        logger.info("\nResolving dependency graph...")
        for target in targets:
            self.targets[target] = self.resolve_target_images(target)

        for target in targets:
            logger.info(f"\nBuilding [{target}] target...")
            self.build_target_image(target)

    def push(self) -> None:
        logger.info("\nPushing images...")
        for image in self.images.values():
            if image.loaded:
                if image.was_pulled:
                    image.logger.info(f"{image.name} Skipping push of pulled image")
                else:
                    image.logger.info(f"{image.name} Trying push...")
                    image.push()
