from abc import ABC, abstractmethod


class PlatformConverter(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def translate(
        self,
        instance: dict,
        translator_type: str,
    ) -> dict:
        pass

    @abstractmethod
    def can_handle(self, asset_type: str) -> bool:
        pass

    @abstractmethod
    def translate_all(self) -> list[tuple[dict, str]]:
        pass

    @abstractmethod
    def update_assets_status(
        self,
        success: list[str],
        failed: list[str]
    ) -> None:
        pass

    @abstractmethod
    def get_asset_id(self, asset: dict) -> str:
        pass
