import argparse
import datetime
import json
import sys
import time
import traceback
from typing import List, Tuple

from . import constants as C
from . import __version__ as VERSION
from .color import color
from .config import Config
from .logger import logger
from .image import DockerImage, FakeImage, ImageFactory, ImageGraph


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
        "--monochrome",
        "-m",
        dest="color",
        action="store_false",
        help="Don't colorize log messages",
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


def parse_args(args: List[str]) -> Tuple[argparse.Namespace, Config]:
    options = parse_options(args)

    if not options.color:
        color.enabled = False

    logger.info(color.magenta(f"\nContainer Prefab v:{VERSION}"))
    logger.info(f"Called with args: {color.green(json.dumps(args))}")
    logger.info(f"Loading config file: {color.green(options.config_file)}")
    config = Config.from_yaml_filepath(options.config_file)

    logger.info(color.magenta("\nConfig options:"))
    config.display_options()

    return options, config


def elapsed_time(monotonic_start: float) -> str:
    elapsed_time = datetime.timedelta(seconds=time.monotonic() - monotonic_start)

    if elapsed_time.seconds < 10:
        award = "🛸"
    elif elapsed_time.seconds < 60:
        award = "🚀"
    elif elapsed_time.seconds < 120:
        award = "🥇"
    elif elapsed_time.seconds < 180:
        award = "🥈"
    elif elapsed_time.seconds < 240:
        award = "🥉"
    else:
        award = "🐢"

    return f"{str(elapsed_time)[:-4]} {award}"


def cli(args: List[str]) -> None:
    build_start_time = time.monotonic()
    options, config = parse_args(args)

    image_constructor = FakeImage if options.noop else DockerImage
    image_factory = ImageFactory(config, options.repo, options.tags, image_constructor)
    image_graph = ImageGraph(config, image_factory)
    image_graph.build(options.targets)
    logger.info(
        f"\n{color.green('Build elapsed time:')} {elapsed_time(build_start_time)}\n"
    )

    if options.push:
        push_start_time = time.monotonic()
        image_graph.push()
        logger.info(
            f"\n{color.green('Push elapsed time: ')} {elapsed_time(push_start_time)}"
        )
        logger.info(
            f"{color.green('Total elapsed time:')} {elapsed_time(build_start_time)}\n"
        )


def main() -> None:
    try:
        cli(sys.argv[1:])
        status = 0
    except Exception:
        logger.error(color.red(traceback.format_exc()))
        status = 1
    sys.exit(status)
