import json
from typing import Any, Callable, Dict, List, Tuple

from . import errors as E
from .color import color
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
            image.logger.info(f"target_image {color.yellow(image.name)}")

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
                vectors.append(vector)
                self._resolve_target_images(dependent, images, vectors)
                vectors.pop()

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
            image.logger.info(f"{color.yellow(image.name)} Trying pull...")
            image.pull()
        except Exception as error:
            if not isinstance(error, self.allowed_pull_errors):
                raise
            else:
                error_name = type(error).__name__
                error_message = color.red(f"{error_name}: {error}")
                image.logger.info(f"{color.yellow(image.name)} {error_message}")
                image.logger.info(
                    f"{color.yellow(image.name)} {error_name} in allowed_pull_errors, continuing..."
                )

    def _load_target_image(self, image: Image) -> bool:
        if image.is_loaded:
            image.logger.info(f"{color.yellow(image.name)} Image loaded")
        else:
            image.logger.info(f"{color.yellow(image.name)} Image not loaded")
            self.pull_target_image(image)

        if image.is_loaded and self.config.validate_image:
            image.validate()
            image.logger.info(f"{color.yellow(image.name)} Image validated")

        return image.is_loaded

    def load_target_image(self, image: Image) -> bool:
        is_loaded = False

        try:
            is_loaded = self._load_target_image(image)
        except E.ImageValidationError as error:
            if not self.config.build_on_validate_error:
                raise
            else:
                error_message = color.red(f"ImageValidationError: {error}")
                image.logger.warning(f"{color.yellow(image.name)} {error_message}")
                image.logger.warning(
                    f"{color.yellow(image.name)} build_on_validate_error enabled, continuing..."
                )

        return is_loaded

    @staticmethod
    def display_image_build_options(image: Image) -> None:
        json_text = json.dumps(image.build_options, sort_keys=True, indent=4)
        json_lines = json_text.splitlines()
        image.logger.info(
            f"{color.yellow(image.name)} build_options {color.green(json_lines.pop(0))}"
        )

        for line in json_lines:
            image.logger.info(color.green(line))

    def should_build_target_image(self, target: str) -> bool:
        # image must be built if any upstream dependencies were (re)built
        return any(image for image in self.targets[target] if image.was_built)

    def _build_image(self, image: Image) -> None:
        image.logger.info(f"{color.yellow(image.name)} Trying build...")
        self.display_image_build_options(image)
        image.build()

        if self.config.prune_after_build:
            image.prune()

    def build_target_images(self, target: str) -> None:
        for image in self.targets[target]:
            if self.should_build_target_image(target):
                self._build_image(image)
                continue

            if not self.load_target_image(image):
                self._build_image(image)

    def display_build_target(self, target: str) -> None:
        images = dict(map(reversed, self.images.items()))
        targets = [color.cyan(f"[{images[image]}]") for image in self.targets[target]]

        if len(targets) > 1:
            build_order = color.magenta("using build order ")
            build_order += color.magenta(", ").join(targets)
        else:
            build_order = ""

        logger.info(
            "\n{0} {1} {2} {3}".format(
                color.magenta("Building"),
                color.cyan(f"[{target}]"),
                color.magenta("target"),
                build_order,
            )
        )

    def build(self, targets: List[str]) -> None:
        logger.info(color.magenta("\nResolving dependency graph"))

        for target in targets:
            self.targets[target] = self.resolve_target_images(target)

        for target in targets:
            self.display_build_target(target)
            self.build_target_images(target)

    def push(self) -> None:
        logger.info(color.magenta("\nPushing images"))

        for image in self.images.values():
            if image.is_loaded:
                if image.was_pulled and not image.was_built:
                    image.logger.info(
                        f"{color.yellow(image.name)} Skipping push of pulled image"
                    )
                else:
                    image.logger.info(f"{color.yellow(image.name)} Trying push...")
                    image.push()
