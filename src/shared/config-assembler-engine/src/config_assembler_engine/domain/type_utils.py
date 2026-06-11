from typing import Annotated, Any, get_args, get_origin


def unwrap_optional(tp: Any) -> Any:
    if tp is None:
        return tp

    origin = get_origin(tp)
    args = get_args(tp)

    if origin is not None and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return unwrap_optional(non_none[0])

    if origin is Annotated:
        return unwrap_optional(args[0]) if args else tp

    return tp
