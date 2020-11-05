from dataclasses import dataclass
from typing import Optional

from .docker import DockerImage


@dataclass
class RaiseOn:
    pull: Optional[Exception]
    validate: Optional[Exception]
    build: Optional[Exception]
    push: Optional[Exception]


class FakeImage(DockerImage):
    def __init__(
        self,
        *args,
        loaded=False,
        pull=None,
        validate=None,
        build=None,
        push=None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.raise_on = RaiseOn(pull, validate, build, push)
        self._loaded = loaded

    def pull(self) -> None:
        if self.raise_on.pull:
            raise self.raise_on.pull

        self._pull_success()

    def validate(self) -> None:
        if self.raise_on.validate:
            raise self.raise_on.validate

    def build(self) -> None:
        if self.raise_on.build:
            raise self.raise_on.build

        self._build_success()

    def push(self) -> None:
        if self.raise_on.push:
            raise self.raise_on.push

        self.logger.info(f"{self.name} Pushed")
