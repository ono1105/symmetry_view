from __future__ import annotations


_MAPPING_CACHE_BY_LIST_ID: dict[int, tuple[int, dict[int, dict]]] = {}
_OPERATION_CACHE_BY_LIST_ID: dict[int, tuple[int, dict[int, dict]]] = {}


def selected_mapping(atom_mappings: dict | None, operation_index: int | None) -> dict | None:
    if atom_mappings is None or operation_index is None:
        return None
    mappings = atom_mappings.get("mappings", [])
    cache_key = id(mappings)
    cached = _MAPPING_CACHE_BY_LIST_ID.get(cache_key)
    if cached is None or cached[0] != len(mappings):
        cached = (len(mappings), {mapping["operation_index"]: mapping for mapping in mappings})
        _MAPPING_CACHE_BY_LIST_ID[cache_key] = cached
    return cached[1].get(operation_index)


def filter_by_operation(elements: list[dict], operation_index: int | None) -> list[dict]:
    if operation_index is None:
        return elements
    return [
        element
        for element in elements
        if operation_index in element.get("operation_indices", [])
    ]


def selected_elements(elements: list[dict], operation_index: int | None, element_index: int | None) -> list[dict]:
    filtered = filter_by_operation(elements, operation_index)
    if element_index is None:
        return filtered
    if element_index < 0 or element_index >= len(filtered):
        return []
    return [filtered[element_index]]


def has_element_index(render_data: dict, operation_index: int, element_index: int) -> bool:
    return any(
        0 <= element_index < len(filter_by_operation(render_data[key], operation_index))
        for key in ("axes", "planes", "centers")
    )


def operation_by_index(operations: list[dict], operation_index: int) -> dict | None:
    cache_key = id(operations)
    cached = _OPERATION_CACHE_BY_LIST_ID.get(cache_key)
    if cached is None or cached[0] != len(operations):
        cached = (len(operations), {operation["index"]: operation for operation in operations})
        _OPERATION_CACHE_BY_LIST_ID[cache_key] = cached
    return cached[1].get(operation_index)
