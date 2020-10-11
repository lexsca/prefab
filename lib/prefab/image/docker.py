import json
import logging
from typing import Any, Dict, Generator, Optional, Union

import docker

from .. import errors as E
from ..logger import logger


class DockerImage:
    def __init__(
        self,
        repo: str,
        tag: str,
        build_options: Dict[str, Any],
        docker_client: Optional[docker.client.DockerClient] = None,
        logger: Union[logging.Logger, logging.LoggerAdapter] = logger,
    ) -> None:
        self.repo: str = repo
        self.tag: str = tag
        self.build_options: Dict[str, Any] = build_options
        self.logger: Union[logging.Logger, logging.LoggerAdapter] = logger
        self._loaded: Optional[bool] = None
        self.was_pulled: bool = False
        self.was_built: bool = False

        if docker_client is None:
            docker_client = docker.from_env(version="auto")

        self.docker_client: docker.client.DockerClient = docker_client

    def _log_transfer_message(self, log_entry) -> None:
        if "id" in log_entry:
            message = f"{log_entry.get('id')}: {log_entry.get('status')}"
        else:
            message = str(log_entry["status"])

        self.logger.info(message)

    def _log_stream_decoder(
        self, chunker: Generator[bytes, None, None]
    ) -> Generator[Dict[str, Any], None, None]:
        for chunk in chunker:
            for line in chunk.splitlines():
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.decoder.JSONDecodeError:
                    self.logger.warning(f"Skipping malformed log entry: {chunk}")

    def _process_transfer_log_stream(
        self, log_stream: Generator[Dict[str, Any], None, None]
    ) -> None:
        for log_entry in self._log_stream_decoder(log_stream):
            if log_entry.get("error"):
                raise E.ImageAccessError(log_entry["error"])

            if "status" not in log_entry or log_entry.get("progressDetail"):
                continue

            self._log_transfer_message(log_entry)

    def _get_docker_image(self) -> Optional[docker.models.images.Image]:
        docker_image = None

        for image in self.docker_client.images.list(name=self.repo):
            if self.name in image.tags:
                docker_image = image
                break

        if docker_image is None:
            raise E.ImageNotFoundError(f"{self.name} not found")

        return docker_image

    @property
    def name(self) -> str:
        return f"{self.repo}:{self.tag}"

    @property
    def is_loaded(self) -> bool:
        if self._loaded is None:
            try:
                self._get_docker_image()
                self._loaded = True
            except E.ImageNotFoundError:
                self._loaded = False

        return self._loaded

    def _pull_success(self) -> None:
        self._loaded = True
        self.was_pulled = True

    def pull(self) -> None:
        try:
            log_stream = self.docker_client.api.pull(
                repository=self.repo, tag=self.tag, stream=True, decode=False
            )
            self._process_transfer_log_stream(log_stream)
            self._pull_success()
        except docker.errors.NotFound as error:
            raise E.ImageNotFoundError(error.explanation)
        except docker.errors.APIError as error:
            raise E.ImageAccessError(error.explanation)

    def validate(self) -> None:
        docker_image = self._get_docker_image()

        for name, expected in self.build_options["labels"].items():
            result = docker_image.labels.get(name)
            if result != expected:
                raise E.ImageValidationError(
                    f'{self.name} label "{name}" '
                    f'expected value "{expected}", got "{result}"'
                )

    def _build(self) -> Generator[Dict[str, Any], None, None]:
        try:
            log_stream = self.docker_client.api.build(**self.build_options)
        except docker.errors.APIError as error:
            raise E.ImageBuildError(str(error))
        return log_stream

    def _build_success(self) -> None:
        self.logger.info(f"{self.name} Build succeeded")
        self.was_built = True
        self._loaded = True

    def build(self) -> None:
        log_stream = self._build()

        for log_entry in log_stream:
            if "error" in log_entry:
                raise E.ImageBuildError(log_entry["error"])
            if message := log_entry.get("stream", "").strip():
                self.logger.info(message)

        self._build_success()

    def prune(self) -> None:
        try:
            self.docker_client.api.prune_images(filters={"dangling": True})
        except Exception as error:
            self.logger.warning(f"Prune dangling images failed: {error}")

    def push(self) -> None:
        try:
            log_stream = self.docker_client.images.push(
                repository=self.repo, tag=self.tag, stream=True, decode=False
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.APIError as error:
            raise E.ImagePushError(str(error))

    def remove(self, force: bool = False, noprune: bool = False) -> None:
        docker_image = self._get_docker_image()
        self.docker_client.images.remove(docker_image.id, force, noprune)
