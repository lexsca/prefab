class PrefabError(Exception):
    pass


class HashAlgorithmNotFound(PrefabError):
    pass


class ImageAccessError(PrefabError):
    pass


class ImageBuildError(PrefabError):
    pass


class ImageNotFoundError(PrefabError):
    pass


class ImagePushError(PrefabError):
    pass


class ImageValidationError(PrefabError):
    pass


class InvalidConfigError(PrefabError):
    pass


class TargetCyclicError(PrefabError):
    pass


class TargetNotFoundError(PrefabError):
    pass
