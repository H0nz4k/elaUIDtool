"""Modely zobrazené při exportu; systémové rodiny vybírá AppBlaster z MultiBIX."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReaderModel:
    key: str
    name: str
    description: str
    image: str
    product_url: str


READER_MODELS = (
    ReaderModel(
        "multitech2-usb", "TWN4 MULTITECH 2 USB",
        "Stolní čtečka s USB kabelem · LF + HF",
        "twn4-multitech-2-usb.jpg",
        "https://www.elatec-rfid.com/int/product-detail/twn4-multitech-2",
    ),
    ReaderModel(
        "multitech3-m-lf-hf", "TWN4 MULTITECH 3 M LF HF",
        "Vestavný modul · LF + HF · export pro USB CDC",
        "twn4-multitech-3-m-lf-hf.png",
        "https://www.elatec-rfid.com/int/product-detail/twn4-multitech-3-m-lf-hf",
    ),
)
DEFAULT_READER_MODEL = READER_MODELS[0].key


def get_reader_model(key: str) -> ReaderModel:
    for model in READER_MODELS:
        if model.key == key:
            return model
    raise ValueError(f"Neznámý model čtečky: {key}")
