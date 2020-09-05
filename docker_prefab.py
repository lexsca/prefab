import argparse
import hashlib
import logging
import sys

import docker
import yaml


logger = logging.getLogger(__name__)
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)

DEFAULT_ALGORITHM = "sha256"
DEFAULT_LABEL = "prefab.digest"
DEFAULT_CHUNK_SIZE = 65535
DEFAULT_CONFIG_FILE = "prefab.yml"
SHORT_DIGEST_SIZE = 12


class DockerPrefabError(Exception):
    pass


class ImageAccessError(DockerPrefabError):
    pass


class ImageBuildError(DockerPrefabError):
    pass


class ImageNotFoundError(DockerPrefabError):
    pass


class ImagePushError(DockerPrefabError):
    pass


class ImageVerifyError(DockerPrefabError):
    pass


class TargetCyclicError(DockerPrefabError):
    pass


class TargetNotFoundError(DockerPrefabError):
    pass


class Image:
    def __init__(self, repo, tag, build_options=None):
        self.repo = repo
        self.tag = tag
        self.build_options = build_options
        self.docker_client = docker.from_env(version="auto")

    @staticmethod
    def _process_transfer_log_stream(log_stream):
        for log_entry in log_stream:
            if "error" in log_entry:
                raise ImageAccessError(log_entry["error"])
            if "status" not in log_entry or log_entry.get("progressDetail"):
                continue
            if "id" in log_entry:
                message = f"{log_entry.get('id')}: {log_entry.get('status')}"
            else:
                message = log_entry["status"]
            logger.info(message)

    @property
    def name(self):
        return f"{self.repo}:{self.tag}"

    def pull(self):
        try:
            logger.info(f"Pulling {self.name}")
            log_stream = self.docker_client.api.pull(
                self.name, self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.NotFound as error:
            raise ImageNotFoundError(str(error))
        except docker.errors.APIError as error:
            raise ImageAccessError(str(error))

    def _build(self):
        build_options = {
            "dockerfile": "Dockerfile",
            "tag": self.name,
            "path": ".",
            "rm": True,
            "forcerm": True,
            "decode": True,
        }
        if self.build_options is not None:
            build_options.update(self.build_options)
        try:
            logger.info(f"Building {self.name}")
            log_stream = self.docker_client.api.build(**build_options)
        except docker.errors.APIError as error:
            raise ImageBuildError(str(error))
        return log_stream

    def build(self):
        log_stream = self._build()
        for log_entry in log_stream:
            if "error" in log_entry:
                raise ImageBuildError(log_entry["error"])
            if message := log_entry.get("stream", "").strip():
                logger.info(message)

    def push(self):
        try:
            logger.info(f"Pushing {self.name}")
            log_stream = self.docker_client.images.push(
                repository=self.repo, tag=self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.APIError as error:
            raise ImagePushError(str(error))

    def verify(self, label, value):
        image = self.docker_client.images.get(self.name)
        if image.labels.get(label) != value:
            raise ImageVerifyError(
                f"{label}: expected {value}, got: {image.labels.get(label)}"
            )
        return True


class ImageTree:
    def __init__(self, repo, targets, config):
        self.repo = repo
        self.targets = targets
        self.config = config
        self.images = {}
        self.digests = {}
        # TODO create tree of Image instances

        # roughed out build_options:
        # build_options: {
        #     labels: {
        #         prefab.digest: sha256:9717f7c6656b647fad3fc0979cf...
        #     }
        #     buildargs: {
        #         prefab_target: quay.io/lexsca/prefab:deadbeef1234
        #         prefab_base: quay.io/lexsca/prefab:9717f7c6656b
        #     }
        # }

    def resolve_target_dependencies(self, target, dependencies=None, vectors=None):
        targets = self.config.get("targets", {})
        if target not in targets:
            raise TargetNotFoundError(f"{target}: not found")

        if dependencies is None:
            dependencies = []
        if vectors is None:
            vectors = []

        for dependent in targets.get(target).get("depends_on", []):
            vector = (target, dependent)
            if vector in vectors:
                raise TargetCyclicError(f"{target}: has circular dependencies")
            else:
                checkpoint = len(vectors)
                vectors.append(vector)
                self.resolve_target_dependencies(dependent, dependencies, vectors)
                del vectors[checkpoint:]

            if dependent not in dependencies:
                dependencies.append(dependent)

        return dependencies

    def resolve_target_build_order(self, target):
        dependencies = self.resolve_target_dependencies(target)
        dependencies.append(target)
        return dependencies

    def build(self):
        for target in self.targets:
            target, _, tag = target.partition(":")
            build_order = self.resolve_target_build_order(target)
            logger.info(build_order)

    def push(self):
        logger.info("push")


def parse_config(path):
    with open(path) as raw_config:
        config = yaml.safe_load(raw_config)
    return config


def parse_options(args):
    description = "Efficiently build docker images"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        "-c",
        dest="config_file",
        action="store",
        metavar="PATH",
        default=DEFAULT_CONFIG_FILE,
        help="Prefab config file to use",
    )
    parser.add_argument(
        "--push",
        "-p",
        action="store_true",
        help="Push images to repo after building",
    )
    parser.add_argument(
        "--repo",
        "-r",
        dest="repo",
        action="store",
        metavar="URI",
        required=True,
        help="Image repo to use (e.g. quay.io/lexsca/prefab)",
    )
    parser.add_argument(
        "--target",
        "-t",
        dest="targets",
        action="append",
        required=True,
        metavar="NAME[:TAG]",
        help="Image target(s) to build with optional image tag",
    )
    return parser.parse_args(args)


def main(args):
    options = parse_options(args)
    config = parse_config(options.config_file)
    image_tree = ImageTree(options.repo, options.targets, config)
    image_tree.build()
    if options.push:
        image_tree.push()


def _main():
    if __name__ == "__main__":
        main(sys.argv[1:])


_main()
