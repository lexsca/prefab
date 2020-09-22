class DockerPrefabError(Exception):
    pass


class HashAlgorithmNotFound(DockerPrefabError):
    pass


class ImageAccessError(DockerPrefabError):
    pass


class ImageBuildError(DockerPrefabError):
    pass


class ImageNotFoundError(DockerPrefabError):
    pass


class ImagePushError(DockerPrefabError):
    pass


class ImageValidationError(DockerPrefabError):
    pass


class InvalidConfigError(DockerPrefabError):
    pass


class TargetTagError(DockerPrefabError):
    pass


class TargetCyclicError(DockerPrefabError):
    pass


class TargetNotFoundError(DockerPrefabError):
    pass
