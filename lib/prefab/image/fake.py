import collections

from .docker import DockerImage


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
        raise_on = collections.namedtuple("RaiseOn", "pull validate build push")
        self._raise_on = raise_on(pull, validate, build, push)
        self._loaded = loaded

    def pull(self) -> None:
        if self._raise_on.pull:
            raise self._raise_on.pull

        self._pull_success()

    def validate(self) -> None:
        if self._raise_on.validate:
            raise self._raise_on.validate

    def build(self) -> None:
        if self._raise_on.build:
            raise self._raise_on.build

        self._build_success()

    def push(self) -> None:
        if self._raise_on.push:
            raise self._raise_on.push

        self.logger.info(f"{self.name} Pushed")
