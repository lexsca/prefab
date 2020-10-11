class ContainerPrefabError(Exception):
    pass


class HashAlgorithmNotFound(ContainerPrefabError):
    pass


class ImageAccessError(ContainerPrefabError):
    pass


class ImageBuildError(ContainerPrefabError):
    pass


class ImageNotFoundError(ContainerPrefabError):
    pass


class ImagePushError(ContainerPrefabError):
    pass


class ImageValidationError(ContainerPrefabError):
    pass


class InvalidConfigError(ContainerPrefabError):
    pass


class TargetCyclicError(ContainerPrefabError):
    pass


class TargetNotFoundError(ContainerPrefabError):
    pass
