import fnmatch
import os
from typing import List, Tuple


def parse_ignore_patterns(patterns: List[str]) -> Tuple[List[str], List[str]]:
    file_patterns: List[str] = []
    dir_patterns: List[str] = []

    for pattern in patterns:
        if pattern.endswith("/"):
            dir_patterns.append(pattern[:-1])
        else:
            dir_patterns.append(pattern)
            file_patterns.append(pattern)

    return dir_patterns, file_patterns


def cull_dirs(
    base_dir: str,
    dir_names: List[str],
    file_names: List[str],
    ignore_patterns: List[str],
) -> None:
    ignore_dirs = set()

    for pattern in ignore_patterns:
        if fnmatch.fnmatch(base_dir, pattern):
            dir_names.clear()
            file_names.clear()
            ignore_dirs.clear()
            break

        for dir_name in fnmatch.filter(dir_names, pattern):
            ignore_dirs.add(dir_name)

    for dir_name in ignore_dirs:
        dir_names.remove(dir_name)


def filter_files(
    base_dir: str, file_names: List[str], ignore_patterns: List[str]
) -> List[str]:
    file_paths = []
    ignore_names = set()

    for ignore_pattern in ignore_patterns:
        for file_name in fnmatch.filter(file_names, ignore_pattern):
            ignore_names.add(file_name)

    for file_name in set(file_names) - ignore_names:
        file_paths.append(os.path.join(base_dir, file_name))

    for pattern in ignore_patterns:
        for file_path in fnmatch.filter(file_paths, pattern):
            file_paths.remove(file_path)

    return file_paths


def walk(path: str, ignore_patterns: List[str]) -> List[str]:
    file_paths = []
    norm_path = os.path.normpath(path)
    dir_ignore_patterns, file_ignore_patterns = parse_ignore_patterns(ignore_patterns)

    def onerror(error):
        raise error

    for base_dir, dir_names, file_names in os.walk(
        norm_path, topdown=True, onerror=onerror
    ):
        cull_dirs(base_dir, dir_names, file_names, dir_ignore_patterns)
        file_paths.extend(filter_files(base_dir, file_names, file_ignore_patterns))

    return sorted(file_paths)
