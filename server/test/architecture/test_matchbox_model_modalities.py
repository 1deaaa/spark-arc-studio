from types import SimpleNamespace

from llm.agen_matchbox.models import (
    MODALITY_EMBEDDING,
    MODALITY_IMAGE,
    MODALITY_TEXT,
    get_model_modalities,
    is_chat_model,
    is_embedding_model,
    is_image_generation_model,
    model_accepts,
    model_outputs,
    normalize_model_modalities,
    set_model_modalities,
)


def test_default_model_is_text_in_and_text_out() -> None:
    input_modalities, output_modalities = normalize_model_modalities()

    assert input_modalities == [MODALITY_TEXT]
    assert output_modalities == [MODALITY_TEXT]


def test_modalities_express_vision_generation_and_unified_output() -> None:
    input_modalities, output_modalities = normalize_model_modalities(
        [MODALITY_IMAGE, MODALITY_TEXT],
        [MODALITY_IMAGE, MODALITY_TEXT],
    )

    assert input_modalities == [MODALITY_TEXT, MODALITY_IMAGE]
    assert output_modalities == [MODALITY_TEXT, MODALITY_IMAGE]


def test_embedding_output_is_exclusive_and_forces_text_input() -> None:
    input_modalities, output_modalities = normalize_model_modalities(
        [MODALITY_TEXT, MODALITY_IMAGE],
        [MODALITY_TEXT, MODALITY_IMAGE, MODALITY_EMBEDDING],
    )

    assert input_modalities == [MODALITY_TEXT]
    assert output_modalities == [MODALITY_EMBEDDING]


def test_model_helpers_derive_business_types_from_modalities() -> None:
    model = SimpleNamespace(input_modalities=None, output_modalities=None)
    stored = set_model_modalities(
        model,
        [MODALITY_TEXT, MODALITY_IMAGE],
        [MODALITY_TEXT, MODALITY_IMAGE],
    )

    assert stored == {
        "input_modalities": [MODALITY_TEXT, MODALITY_IMAGE],
        "output_modalities": [MODALITY_TEXT, MODALITY_IMAGE],
    }
    assert get_model_modalities(model) == stored
    assert model_accepts(model, MODALITY_IMAGE)
    assert model_outputs(model, MODALITY_TEXT)
    assert model_outputs(model, MODALITY_IMAGE)
    assert is_chat_model(model)
    assert is_image_generation_model(model)
    assert not is_embedding_model(model)


def test_embedding_model_is_not_selected_as_chat_or_image_model() -> None:
    model = SimpleNamespace(input_modalities=None, output_modalities=None)
    set_model_modalities(model, [MODALITY_TEXT], [MODALITY_EMBEDDING])

    assert is_embedding_model(model)
    assert not is_chat_model(model)
    assert not is_image_generation_model(model)
