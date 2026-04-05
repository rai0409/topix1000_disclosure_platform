from __future__ import annotations


class EdinetDownloaderError(RuntimeError):
    pass


class EdinetApiKeyMissingError(EdinetDownloaderError):
    pass


class EdinetApiResponseError(EdinetDownloaderError):
    pass
