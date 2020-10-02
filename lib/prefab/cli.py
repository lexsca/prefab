import argparse
import datetime
import sys
import time
import traceback
from typing import List

from . import constants as C
from .config import Config
from .logger import logger
from .image import Image, FakeImage
from .image_factory import ImageFactory
from .image_graph import ImageGraph


def parse_options(args: List[str]) -> argparse.Namespace:
    description = "efficiently build container images"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        "-c",
        dest="config_file",
        action="store",
        metavar="PATH",
        default=C.DEFAULT_CONFIG_FILE,
        help="Target build config file to use",
    )
    parser.add_argument(
        "--dry-run",
        dest="noop",
        action="store_true",
        help="Show how targets would be built",
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
        dest="_targets",
        action="append",
        required=True,
        metavar="NAME[:TAG]",
        help="Image target(s) to build with optional custom image tag",
    )

    options = parser.parse_args(args)
    options.tags = dict()
    options.targets = []
    tag_set = set()

    for target in options._targets:
        target, _, tag = target.partition(":")
        options.targets.append(target)
        if tag and tag in tag_set:
            parser.exit(
                status=2, message=f"{parser.format_help()}\nDuplicate tag: {tag}\n"
            )
        elif tag:
            options.tags[target] = tag
            tag_set.add(tag)

    return options


def elapsed_time(monotonic_start: float) -> str:
    elapsed_time = datetime.timedelta(seconds=time.monotonic() - monotonic_start)
    return str(elapsed_time)[:-4]


def cli(args: List[str]) -> None:
    build_start_time = time.monotonic()

    options = parse_options(args)
    logger.info(f"Called with args: {args}")
    config = Config.from_yaml_filepath(options.config_file)

    image_constructor = FakeImage if options.noop else Image
    image_factory = ImageFactory(config, options.repo, options.tags, image_constructor)
    image_graph = ImageGraph(config, image_factory)
    image_graph.build(options.targets)
    logger.info(f"\nBuild elapsed time: {elapsed_time(build_start_time)}")

    if options.push:
        push_start_time = time.monotonic()
        image_graph.push()
        logger.info(f"\nPush elapsed time: {elapsed_time(push_start_time)}")
        logger.info(f"\nTotal elapsed time: {elapsed_time(build_start_time)}")


def main() -> None:
    try:
        cli(sys.argv[1:])
        status = 0
    except Exception:
        logger.error(traceback.format_exc())
        status = 1
    sys.exit(status)
