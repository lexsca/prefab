import json
from typing import Any, Callable, Dict, List, Tuple

from .. import errors as E
from ..color import color
from ..config import Config
from ..logger import logger
from .docker import DockerImage


class ImageGraph:
    def __init__(self, config: Config, image_factory: Callable) -> None:
        self.config: Config = config
        self.image_factory: Callable = image_factory
        self.images: Dict[str, DockerImage] = {}

    def configure_target_image(self, target: str) -> None:
        if target not in self.images:
            image = self.images[target] = self.image_factory(target)
            image.logger.info(f"target_image {color.image(image.name)}")

    def _resolve_target_dependencies(
        self, target: str, dependencies: List[str], vectors: List[Tuple[str, str]]
    ) -> List[str]:
        # use a depth-first search to unroll dependencies and detect loops
        for dependent in self.config.get_target(target).get("depends_on", []):
            vector = (target, dependent)
            if vector in vectors:
                raise E.TargetCyclicError(
                    f"Target [{target}] has circular dependencies"
                )
            else:
                vectors.append(vector)
                self._resolve_target_dependencies(dependent, dependencies, vectors)
                vectors.pop()

        self.configure_target_image(target)
        if target not in dependencies:
            dependencies.append(target)

        return dependencies

    def resolve_target_dependencies(self, target: str) -> List[DockerImage]:
        return self._resolve_target_dependencies(
            target=target, dependencies=[], vectors=[]
        )

    @property
    def allowed_pull_errors(self) -> Tuple[Any, ...]:
        allowed_error_names = self.config.allowed_pull_errors
        return tuple(getattr(E, name) for name in dir(E) if name in allowed_error_names)

    def pull_target_image(self, image: DockerImage) -> None:
        try:
            image.logger.info(f"{color.image(image.name)} Trying pull...")
            image.pull()
        except Exception as error:
            if not isinstance(error, self.allowed_pull_errors):
                raise
            else:
                error_name = type(error).__name__
                error_message = color.error(f"{error_name}: {error}")
                image.logger.info(f"{color.image(image.name)} {error_message}")
                image.logger.info(
                    f"{color.image(image.name)} {error_name} in allowed_pull_errors, continuing..."
                )

    def _load_target_image(self, image: DockerImage) -> bool:
        if image.is_loaded:
            image.logger.info(f"{color.image(image.name)} Image loaded")
        else:
            image.logger.info(f"{color.image(image.name)} Image not loaded")
            self.pull_target_image(image)

        if image.is_loaded and self.config.validate_image:
            image.validate()
            image.logger.info(f"{color.image(image.name)} Image validated")

        return image.is_loaded

    def load_target_image(self, image: DockerImage) -> bool:
        is_loaded = False

        try:
            is_loaded = self._load_target_image(image)
        except E.ImageValidationError as error:
            if not self.config.build_on_validate_error:
                raise
            else:
                error_message = color.error(f"ImageValidationError: {error}")
                image.logger.warning(f"{color.image(image.name)} {error_message}")
                image.logger.warning(
                    f"{color.image(image.name)} build_on_validate_error enabled, continuing..."
                )

        return is_loaded

    @staticmethod
    def display_image_build_options(image: DockerImage) -> None:
        json_text = json.dumps(image.build_options, sort_keys=True, indent=4)
        json_lines = json_text.splitlines()
        image.logger.info(
            f"{color.image(image.name)} build_options {color.config(json_lines.pop(0))}"
        )

        for line in json_lines:
            image.logger.info(color.config(line))

    def _build_image(self, image: DockerImage) -> None:
        image.logger.info(f"{color.image(image.name)} Trying build...")
        self.display_image_build_options(image)
        image.build()

        if self.config.prune_after_build:
            image.prune()

    def build_target_images(self, target: str, force: bool = False) -> None:
        image = self.images[target]

        if force or not self.load_target_image(image):
            for dependent in self.config.get_target(target).get("depends_on", []):
                self.build_target_images(dependent, force)
            self._build_image(image)

    def display_build_target(self, target: str) -> None:
        targets = self.resolve_target_dependencies(target)

        if len(targets) > 1:
            dependencies = color.header(" with dependencies: ")
            dependencies += color.header(", ").join(
                [color.target(f"[{target}]") for target in targets[-2::-1]]
            )
        else:
            dependencies = ""

        logger.info(
            "\n{0} {1} {2}{3}".format(
                color.header("Building"),
                color.target(f"[{target}]"),
                color.header("target"),
                dependencies,
            )
        )

    def resolve_build_targets(self, targets: List[str]) -> None:
        logger.info(color.header("\nResolving build targets"))
        for target in targets:
            self.resolve_target_dependencies(target)

    def build(self, targets: List[str], force: bool = False) -> None:
        self.resolve_build_targets(targets)

        for target in targets:
            self.display_build_target(target)
            self.build_target_images(target, force)

    def push(self, targets: List[str]) -> None:
        logger.info(color.header("Pushing images"))

        for image in [self.images[target] for target in targets]:
            if image.is_loaded:
                if image.was_pulled and not image.was_built:
                    image.logger.info(
                        f"{color.image(image.name)} Skipping push of pulled image"
                    )
                else:
                    image.logger.info(f"{color.image(image.name)} Trying push...")
                    image.push()
