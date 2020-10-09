from .. import errors as E
from .docker import DockerImage


class FakeImage(DockerImage):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._loaded = False

    def pull(self) -> None:
        raise E.ImageNotFoundError(f"{self.name} Not found")

    def validate(self) -> None:
        pass

    def build(self) -> None:
        self._build_success()

    def push(self) -> None:
        self.logger.info(f"{self.name} Pushed")
