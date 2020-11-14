import argparse
import datetime
import json
import sys
import time
import traceback
from typing import Dict, List, Tuple

from . import __version__ as VERSION
from . import constants as C
from . import envfile
from .color import color
from .config import Config
from .logger import logger
from .image import DockerImage, FakeImage, ImageFactory, ImageGraph


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build container images faster ⚡️")

    parser.add_argument(
        "--config",
        "-c",
        dest="config_file",
        action="store",
        metavar="PATH",
        default=C.DEFAULT_CONFIG_FILE,
        help="Target build config file to use (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        dest="noop",
        action="store_true",
        help="Show how targets would be built (implies --force)",
    )
    parser.add_argument(
        "--force",
        dest="force",
        action="store_true",
        help="Force target(s) to be rebuilt",
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
        nargs="+",
        metavar="TARGET_NAME",
        help="Image target(s) to push to repo after building",
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
        nargs="+",
        required=True,
        metavar="TARGET_NAME[:TAG]",
        help="Image target(s) to build with optional custom image tag",
    )

    return parser


def parse_options(args: List[str]) -> argparse.Namespace:
    parser = _arg_parser()
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

    if options.noop:
        options.force = True

    return options


def parse_args(args: List[str]) -> Tuple[argparse.Namespace, Config]:
    options = parse_options(args)
    config = Config.from_yaml_filepath(options.config_file)

    if not options.color:
        color.enabled = False
    else:
        color.style.update(config.color_style)

    logger.info(color.header(f"\nContainer Prefab v:{VERSION}"))
    logger.info(f"Called with args: {color.config(json.dumps(args))}")
    logger.info(f"Loaded config file: {color.config(config.path)}")
    write_envfiles()

    logger.info(color.header("\nConfig options:"))
    config.display_options()

    return options, config


def write_envfiles(envfiles: Dict[str, str] = C.DEFAULT_ENVFILES) -> None:
    for env_key, dest_path in envfiles.items():
        envfile.write(env_key, dest_path)


def elapsed_time(monotonic_start: float) -> str:
    elapsed_time = datetime.timedelta(seconds=time.monotonic() - monotonic_start)
    seconds = elapsed_time.seconds
    category = 1 + (-1 if seconds < 10 else seconds // 60 if seconds < 240 else 4)
    awards = ("⚡", "🚀", "🥇", "🥈", "🥉", "🐢")

    return f"{str(elapsed_time)[:-4]} {awards[category]}"


def cli(args: List[str]) -> None:
    build_start_time = time.monotonic()
    options, config = parse_args(args)

    image_constructor = FakeImage if options.noop else DockerImage
    image_factory = ImageFactory(config, options.repo, options.tags, image_constructor)
    image_graph = ImageGraph(config, image_factory)
    image_graph.build(options.targets, options.force)
    logger.info(
        f"\n{color.elapsed('Build elapsed time:')} {elapsed_time(build_start_time)}\n"
    )

    if options.push:
        push_start_time = time.monotonic()
        image_graph.push(options.push)
        logger.info(
            f"\n{color.elapsed('Push elapsed time: ')} {elapsed_time(push_start_time)}"
        )
        logger.info(
            f"{color.elapsed('Total elapsed time:')} {elapsed_time(build_start_time)}\n"
        )


def main() -> None:
    try:
        cli(sys.argv[1:])
        status = 0
    except Exception:
        logger.error(color.error(traceback.format_exc()))
        status = 1
    sys.exit(status)
